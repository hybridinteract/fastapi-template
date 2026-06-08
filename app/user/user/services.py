"""User services — self-service and admin user management.

Per conventions §4: Services own commit/rollback; CRUD never commits.
Services receive CRUD via constructor (wired in ``app.user.dependencies``).
"""

from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.user.auth.activity import ActivityAction, log_activity
from app.user.auth.crud import OAuthAccountCRUD
from app.user.auth.schemas import MeResponse
from app.user.auth.tokens import get_password_hash
from app.user.enums import UserStatus
from app.user.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.user.permission_management.crud import RoleCRUD
from app.user.user.models import User
from app.user.user.crud import UserCRUD
from app.user.user.query_service import UserQueryService
from app.user.user.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    UserListResponse,
    UserResponse,
    UserUpdateSelf,
    UserWithRolesResponse,
)

logger = get_logger(__name__)


class UserService:
    """Self-service profile reads/updates + cross-module read helpers."""

    def __init__(
        self,
        user_crud: UserCRUD,
        oauth_account_crud: OAuthAccountCRUD,
        user_query_service: UserQueryService,
    ):
        self.user_crud = user_crud
        self.oauth_account_crud = oauth_account_crud
        self.user_query_service = user_query_service

    async def get_my_profile(
        self, session: AsyncSession, user_id: UUID
    ) -> UserResponse:
        # Read-only path → served from cache; invalidated on any profile mutation.
        profile = await self.user_query_service.get_user_by_id(session, user_id)
        if profile is None:
            raise UserNotFoundError(str(user_id))
        return profile

    async def get_me(
        self, session: AsyncSession, current_user: User
    ) -> MeResponse:
        response = MeResponse.model_validate(current_user)

        if current_user.roles:
            response.role = current_user.roles[0].name
            perms: set[str] = set()
            for role in current_user.roles:
                for p in (role.permissions or []):
                    perms.add(p.name)
            response.permissions = sorted(perms)

        response.has_password = bool(current_user.hashed_password)

        oauth_accounts = await self.oauth_account_crud.list_for_user(
            session, current_user.id
        )
        linked: list[str] = [acc.provider for acc in oauth_accounts]
        if current_user.hashed_password and "email_password" not in linked:
            linked.insert(0, "email_password")
        response.linked_providers = linked

        return response

    async def update_my_profile(
        self,
        session: AsyncSession,
        user_id: UUID,
        update_data: UserUpdateSelf,
    ) -> UserResponse:
        user = await self.user_crud.get(session, user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(str(user_id))

        updates = update_data.model_dump(exclude_unset=True)
        if "phone" in updates and updates["phone"] != user.phone:
            if await self.user_crud.get_by_phone(session, updates["phone"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone already in use",
                )

        user = await self.user_crud.update(session, db_obj=user, obj_in=updates)
        await session.commit()
        await UserQueryService.invalidate_user(user_id)
        logger.info(f"User {user_id} updated their profile")
        return UserResponse.model_validate(user)


class AdminService:
    """Admin user management + role assignment to users (bucket 3).

    Role/permission *catalog* management lives in
    ``app.user.permission_management.services.PermissionService``.
    """

    def __init__(
        self,
        user_crud: UserCRUD,
        role_crud: RoleCRUD,
    ):
        self.user_crud = user_crud
        self.role_crud = role_crud

    # ── User CRUD ─────────────────────────────────────────────────────────────

    async def list_users(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        role: Optional[str] = None,
        status_filter: Optional[UserStatus] = None,
        search: Optional[str] = None,
    ) -> UserListResponse:
        users, total = await self.user_crud.list_users_paginated(
            session,
            skip=skip,
            limit=limit,
            role=role,
            status=status_filter,
            search=search,
        )
        return UserListResponse(
            items=[UserWithRolesResponse.model_validate(u) for u in users],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def list_deleted_users(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> UserListResponse:
        users, total = await self.user_crud.list_deleted_users_paginated(
            session, skip=skip, limit=limit, search=search
        )
        return UserListResponse(
            items=[UserWithRolesResponse.model_validate(u) for u in users],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def create_user(
        self,
        session: AsyncSession,
        user_data: AdminUserCreate,
        admin_user: User,
    ) -> UserWithRolesResponse:
        if await self.user_crud.get_by_email(session, user_data.email):
            raise UserAlreadyExistsError(user_data.email)
        if user_data.phone and await self.user_crud.get_by_phone(session, user_data.phone):
            raise UserAlreadyExistsError(f"phone:{user_data.phone}")

        hashed = get_password_hash(user_data.password)
        user = await self.user_crud.create_with_password(
            session, obj_in=user_data, hashed_password=hashed
        )
        await session.commit()

        user = await self.user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} created user {user.email}")
        await log_activity(
            actor_id=admin_user.id,
            action=ActivityAction.CREATE,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=admin_user.full_name,
            details={"email": user.email},
        )
        return UserWithRolesResponse.model_validate(user)

    async def get_user(
        self, session: AsyncSession, user_id: UUID
    ) -> UserWithRolesResponse:
        user = await self.user_crud.get_user_with_roles(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))
        return UserWithRolesResponse.model_validate(user)

    async def update_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        updates: AdminUserUpdate,
        admin_user: User,
    ) -> UserWithRolesResponse:
        user = await self.user_crud.get(session, user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(str(user_id))

        update_data = updates.model_dump(exclude_unset=True)
        if "email" in update_data and update_data["email"] != user.email:
            if await self.user_crud.get_by_email(session, update_data["email"]):
                raise UserAlreadyExistsError(update_data["email"])

        user = await self.user_crud.update(session, db_obj=user, obj_in=update_data)
        await session.commit()
        await UserQueryService.invalidate_user(user_id)

        user = await self.user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} updated user {user_id}")
        await log_activity(
            actor_id=admin_user.id,
            action=ActivityAction.UPDATE,
            resource_type="user",
            resource_id=str(user_id),
            actor_name=admin_user.full_name,
            details={"summary": f"Updated user {user_id}"},
        )
        return UserWithRolesResponse.model_validate(user)

    async def delete_user(
        self, session: AsyncSession, user_id: UUID, admin_user: User
    ) -> None:
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself",
            )

        deleted = await self.user_crud.soft_delete(
            session, user_id=user_id, deleted_by=admin_user.id
        )
        if not deleted:
            raise UserNotFoundError(str(user_id))
        await session.commit()
        await UserQueryService.invalidate_user(user_id)

        logger.info(f"Admin {admin_user.email} soft-deleted user {user_id}")
        await log_activity(
            actor_id=admin_user.id,
            action=ActivityAction.DELETE,
            resource_type="user",
            resource_id=str(user_id),
            actor_name=admin_user.full_name,
        )

    async def restore_user(
        self, session: AsyncSession, user_id: UUID, admin_user: User
    ) -> UserWithRolesResponse:
        user = await self.user_crud.get(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))
        if not user.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not deleted",
            )

        user.is_deleted = False
        user.deleted_at = None
        user.deleted_by_user_id = None
        user.is_active = True
        user.status = UserStatus.ACTIVE
        await session.flush()
        await session.commit()
        await UserQueryService.invalidate_user(user_id)

        user = await self.user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} restored user {user_id}")
        await log_activity(
            actor_id=admin_user.id,
            action=ActivityAction.RESTORE,
            resource_type="user",
            resource_id=str(user_id),
            actor_name=admin_user.full_name,
        )
        return UserWithRolesResponse.model_validate(user)

    async def hard_delete_user(
        self, session: AsyncSession, user_id: UUID, admin_user: User
    ) -> None:
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself",
            )
        user = await self.user_crud.get(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        await session.delete(user)
        await session.commit()
        await UserQueryService.invalidate_user(user_id)
        logger.warning(
            f"Admin {admin_user.email} permanently deleted user {user_id}"
        )

    # ── Role assignment ───────────────────────────────────────────────────────

    async def assign_roles(
        self,
        session: AsyncSession,
        user_id: UUID,
        role_ids: List[UUID],
        admin_user: User,
    ) -> UserWithRolesResponse:
        user = await self.user_crud.get_user_with_roles(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        existing_role_ids = {r.id for r in user.roles}
        for role_id in role_ids:
            if role_id in existing_role_ids:
                continue
            role = await self.role_crud.get(session, role_id)
            if role:
                await self.role_crud.add_user_role(session, user.id, role.id)

        await session.commit()
        await UserQueryService.invalidate_user(user_id)
        user = await self.user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} assigned roles to user {user_id}")
        return UserWithRolesResponse.model_validate(user)

    async def remove_role(
        self,
        session: AsyncSession,
        user_id: UUID,
        role_id: UUID,
        admin_user: User,
    ) -> UserWithRolesResponse:
        link = await self.role_crud.get_user_role_link(session, user_id, role_id)
        if link:
            await self.role_crud.remove_user_role(session, link)
            await session.commit()
            await UserQueryService.invalidate_user(user_id)

        user = await self.user_crud.get_user_with_roles(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        logger.info(
            f"Admin {admin_user.email} removed role {role_id} from user {user_id}"
        )
        return UserWithRolesResponse.model_validate(user)
