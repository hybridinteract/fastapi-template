"""
Admin user management service.

Business logic layer: validation, authorization checks, transaction ownership.
Routes call service methods; service calls CRUD for data access.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.user.models import User, UserStatus
from app.user.crud.user_crud import user_crud
from app.user.crud.role_crud import role_crud
from app.user.crud.permission_crud import permission_crud
from app.user.schemas.admin_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    UserWithRolesResponse,
    UserListResponse,
    RoleWithPermissions,
    PermissionResponse,
)
from app.user.auth_management.utils import get_password_hash
from app.user.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.user.services.user_query_service import UserQueryService
from app.activity import activity, ActivityAction

logger = get_logger(__name__)


class AdminService:
    """Business logic for admin user management."""

    # ── User CRUD ─────────────────────────────────────────────────

    @staticmethod
    async def list_users(
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        role: Optional[str] = None,
        status_filter: Optional[UserStatus] = None,
        search: Optional[str] = None,
    ) -> UserListResponse:
        """List all users with optional filters and pagination."""
        users, total = await user_crud.list_users_paginated(
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

    @staticmethod
    async def create_user(
        session: AsyncSession,
        user_data: AdminUserCreate,
        admin_user: User,
    ) -> UserWithRolesResponse:
        """Create a new user account (no role assigned yet)."""
        existing = await user_crud.get_by_email(session, user_data.email)
        if existing:
            raise UserAlreadyExistsError(user_data.email)

        if user_data.phone:
            existing_phone = await user_crud.get_by_phone(session, user_data.phone)
            if existing_phone:
                raise UserAlreadyExistsError(f"phone:{user_data.phone}")

        hashed_password = get_password_hash(user_data.password)
        user = await user_crud.create_with_password(
            session, obj_in=user_data, hashed_password=hashed_password
        )
        await session.commit()

        # Re-fetch with roles
        user = await user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} created user {user.email}")
        activity.log(
            actor_id=admin_user.id,
            action=ActivityAction.CREATE,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=admin_user.full_name,
            details={"summary": f"Created user account for {user.email}", "email": user.email},
        )
        await UserQueryService.invalidate_user_cache()
        return UserWithRolesResponse.model_validate(user)

    @staticmethod
    async def get_user(session: AsyncSession, user_id: UUID) -> UserWithRolesResponse:
        """Get detailed user info by ID including roles."""
        user = await user_crud.get_user_with_roles(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))
        return UserWithRolesResponse.model_validate(user)

    @staticmethod
    async def update_user(
        session: AsyncSession,
        user_id: UUID,
        updates: AdminUserUpdate,
        admin_user: User,
    ) -> UserWithRolesResponse:
        """Update a user's profile fields."""
        user = await user_crud.get(session, user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(str(user_id))

        update_data = updates.model_dump(exclude_unset=True)

        # Uniqueness check on email
        if "email" in update_data and update_data["email"] != user.email:
            existing = await user_crud.get_by_email(session, update_data["email"])
            if existing:
                raise UserAlreadyExistsError(update_data["email"])

        user = await user_crud.update(session, db_obj=user, obj_in=update_data)
        await session.commit()

        user = await user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} updated user {user_id}")
        activity.log(
            actor_id=admin_user.id,
            action=ActivityAction.UPDATE,
            resource_type="user",
            resource_id=str(user_id),
            actor_name=admin_user.full_name,
            details={"summary": f"Updated user {user_id}"},
        )
        await UserQueryService.invalidate_user_cache(user_id)
        return UserWithRolesResponse.model_validate(user)

    @staticmethod
    async def delete_user(
        session: AsyncSession,
        user_id: UUID,
        admin_user: User,
    ) -> None:
        """Soft-delete a user."""
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself",
            )

        deleted = await user_crud.soft_delete(
            session, user_id=user_id, deleted_by=admin_user.id
        )
        if not deleted:
            raise UserNotFoundError(str(user_id))

        await session.commit()
        logger.info(f"Admin {admin_user.email} deleted user {user_id}")
        activity.log(
            actor_id=admin_user.id,
            action=ActivityAction.DELETE,
            resource_type="user",
            resource_id=str(user_id),
            actor_name=admin_user.full_name,
            details={"summary": f"Deleted user {user_id}"},
        )
        await UserQueryService.invalidate_user_cache(user_id)

    @staticmethod
    async def list_deleted_users(
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> UserListResponse:
        """List all soft-deleted users with pagination."""
        users, total = await user_crud.list_deleted_users_paginated(
            session,
            skip=skip,
            limit=limit,
            search=search,
        )

        return UserListResponse(
            items=[UserWithRolesResponse.model_validate(u) for u in users],
            total=total,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def restore_user(
        session: AsyncSession,
        user_id: UUID,
        admin_user: User,
    ) -> UserWithRolesResponse:
        """Restore a soft-deleted user."""
        # Get user even if deleted
        user = await user_crud.get(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        if not user.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not deleted",
            )

        # Restore the user
        user.is_deleted = False
        user.deleted_at = None
        user.deleted_by_user_id = None
        user.is_active = True
        user.status = UserStatus.ACTIVE

        await session.flush()
        await session.commit()

        user = await user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} restored user {user_id}")
        await UserQueryService.invalidate_user_cache(user_id)
        return UserWithRolesResponse.model_validate(user)

    @staticmethod
    async def hard_delete_user(
        session: AsyncSession,
        user_id: UUID,
        admin_user: User,
    ) -> None:
        """Permanently delete a user from the database."""
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself",
            )

        user = await user_crud.get(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        # Hard delete: permanently remove from database
        await session.delete(user)
        await session.commit()
        logger.warning(f"Admin {admin_user.email} permanently deleted user {user_id}")
        await UserQueryService.invalidate_user_cache(user_id)

    # ── Role Assignment ───────────────────────────────────────────

    @staticmethod
    async def assign_roles(
        session: AsyncSession,
        user_id: UUID,
        role_ids: list[UUID],
        admin_user: User,
    ) -> UserWithRolesResponse:
        """Assign one or more roles to a user."""
        user = await user_crud.get_user_with_roles(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        existing_role_ids = {r.id for r in user.roles}

        for role_id in role_ids:
            if role_id not in existing_role_ids:
                role = await role_crud.get(session, role_id)
                if role:
                    await role_crud.add_user_role(session, user.id, role.id)

        await session.commit()

        user = await user_crud.get_user_with_roles(session, user.id)
        logger.info(f"Admin {admin_user.email} assigned roles to user {user_id}")
        await UserQueryService.invalidate_user_cache(user_id)
        return UserWithRolesResponse.model_validate(user)

    @staticmethod
    async def remove_role(
        session: AsyncSession,
        user_id: UUID,
        role_id: UUID,
        admin_user: User,
    ) -> UserWithRolesResponse:
        """Remove a specific role from a user."""
        link = await role_crud.get_user_role_link(session, user_id, role_id)
        if link:
            await role_crud.remove_user_role(session, link)
            await session.commit()

        user = await user_crud.get_user_with_roles(session, user_id)
        if not user:
            raise UserNotFoundError(str(user_id))

        logger.info(f"Admin {admin_user.email} removed role {role_id} from user {user_id}")
        await UserQueryService.invalidate_user_cache(user_id)
        return UserWithRolesResponse.model_validate(user)

    # ── Roles & Permissions ───────────────────────────────────────

    @staticmethod
    async def list_roles(session: AsyncSession) -> list[RoleWithPermissions]:
        """List all available roles with their permissions."""
        roles = await role_crud.list_with_permissions(session)
        return [RoleWithPermissions.model_validate(r) for r in roles]

    @staticmethod
    async def list_permissions(session: AsyncSession) -> list[PermissionResponse]:
        """List all available permissions."""
        permissions = await permission_crud.list_all(session)
        return [PermissionResponse.model_validate(p) for p in permissions]

    @staticmethod
    async def set_role_permissions(
        session: AsyncSession,
        role_id: UUID,
        permission_ids: list[UUID],
        admin_user: User,
    ) -> RoleWithPermissions:
        """Replace all permissions for a role."""
        role = await role_crud.get_with_permissions(session, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        if role.name == "super_admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify super_admin permissions",
            )

        await permission_crud.replace_role_permissions(session, role_id, permission_ids)
        await session.commit()

        role = await role_crud.get_with_permissions(session, role_id)
        logger.info(f"Admin {admin_user.email} updated permissions for role {role.name}")
        return RoleWithPermissions.model_validate(role)
