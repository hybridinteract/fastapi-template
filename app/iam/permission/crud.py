"""RBAC CRUD — Role, Permission, and user-role links. Never commits.

Per conventions §4: CRUD performs data access only; the service layer owns
commit/rollback.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.iam.permission.models import Permission, Role, RolePermission
from app.iam.user.models import UserRole


# ── Role ────────────────────────────────────────────────────────────────────────

class RoleCRUD:

    async def get(self, session: AsyncSession, role_id: UUID) -> Optional[Role]:
        result = await session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_with_permissions(self, session: AsyncSession, role_id: UUID) -> Optional[Role]:
        result = await session.execute(
            select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, session: AsyncSession, name: str) -> Optional[Role]:
        result = await session.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> List[Role]:
        result = await session.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    async def list_with_permissions(self, session: AsyncSession) -> List[Role]:
        result = await session.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        )
        return list(result.scalars().all())

    async def get_user_role_link(
        self, session: AsyncSession, user_id: UUID, role_id: UUID
    ) -> Optional[UserRole]:
        result = await session.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        return result.scalar_one_or_none()

    async def add_user_role(self, session: AsyncSession, user_id: UUID, role_id: UUID) -> None:
        session.add(UserRole(user_id=user_id, role_id=role_id))
        await session.flush()

    async def remove_user_role(self, session: AsyncSession, user_role: UserRole) -> None:
        await session.delete(user_role)
        await session.flush()


# ── Permission ──────────────────────────────────────────────────────────────────

class PermissionCRUD:

    async def get(self, session: AsyncSession, permission_id: UUID) -> Optional[Permission]:
        result = await session.execute(select(Permission).where(Permission.id == permission_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, session: AsyncSession, name: str) -> Optional[Permission]:
        result = await session.execute(select(Permission).where(Permission.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> List[Permission]:
        result = await session.execute(
            select(Permission).order_by(Permission.resource, Permission.action)
        )
        return list(result.scalars().all())

    async def list_by_role_id(self, session: AsyncSession, role_id: UUID) -> List[Permission]:
        result = await session.execute(
            select(Permission).join(RolePermission).where(RolePermission.role_id == role_id)
        )
        return list(result.scalars().all())

    async def replace_role_permissions(
        self, session: AsyncSession, role_id: UUID, permission_ids: List[UUID]
    ) -> None:
        await session.execute(
            sa_delete(RolePermission).where(RolePermission.role_id == role_id)
        )
        for perm_id in permission_ids:
            perm = await self.get(session, perm_id)
            if perm:
                session.add(RolePermission(role_id=role_id, permission_id=perm_id))
        await session.flush()


# ── Module-level singletons ───────────────────────────────────────────────────

role_crud = RoleCRUD()
permission_crud = PermissionCRUD()
