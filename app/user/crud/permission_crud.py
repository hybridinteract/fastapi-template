"""
Permission CRUD operations.

Data-access layer for Permission table.
No business logic — service layer owns that.
Does NOT commit — service layer owns transactions.
"""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.models import Permission, RolePermission


class PermissionCRUD:
    """CRUD operations for Permission model."""

    async def get(
        self, session: AsyncSession, permission_id: UUID
    ) -> Optional[Permission]:
        """Get a permission by ID."""
        result = await session.execute(
            select(Permission).where(Permission.id == permission_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self, session: AsyncSession, name: str
    ) -> Optional[Permission]:
        """Get permission by name."""
        result = await session.execute(
            select(Permission).where(Permission.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> List[Permission]:
        """List all permissions ordered by resource and action."""
        result = await session.execute(
            select(Permission).order_by(Permission.resource, Permission.action)
        )
        return list(result.scalars().all())

    async def list_by_role_id(
        self, session: AsyncSession, role_id: UUID
    ) -> List[Permission]:
        """Get all permissions for a role."""
        result = await session.execute(
            select(Permission)
            .join(RolePermission)
            .where(RolePermission.role_id == role_id)
        )
        return list(result.scalars().all())

    # ── Role-Permission link operations ───────────────────────────

    async def replace_role_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_ids: List[UUID],
    ) -> None:
        """Replace all permissions for a role. Does NOT commit."""
        # Remove existing
        await session.execute(
            sa_delete(RolePermission).where(RolePermission.role_id == role_id)
        )

        # Add new (validate each permission exists)
        for perm_id in permission_ids:
            perm = await self.get(session, perm_id)
            if perm:
                session.add(RolePermission(role_id=role_id, permission_id=perm_id))

        await session.flush()


permission_crud = PermissionCRUD()
