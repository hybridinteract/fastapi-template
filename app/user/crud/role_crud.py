"""
Role CRUD operations.

Data-access layer for Role table.
No business logic — service layer owns that.
Does NOT commit — service layer owns transactions.
"""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.user.models import Role, UserRole


class RoleCRUD:
    """CRUD operations for Role model."""

    async def get(self, session: AsyncSession, role_id: UUID) -> Optional[Role]:
        """Get role by ID."""
        result = await session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_with_permissions(
        self, session: AsyncSession, role_id: UUID
    ) -> Optional[Role]:
        """Get role with permissions eagerly loaded."""
        result = await session.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self, session: AsyncSession, name: str
    ) -> Optional[Role]:
        """Get role by name."""
        result = await session.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> List[Role]:
        """List all roles ordered by name."""
        result = await session.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    async def list_with_permissions(self, session: AsyncSession) -> List[Role]:
        """List all roles with permissions eagerly loaded."""
        result = await session.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        )
        return list(result.scalars().all())

    # ── User-Role link operations ─────────────────────────────────

    async def get_user_role_link(
        self, session: AsyncSession, user_id: UUID, role_id: UUID
    ) -> Optional[UserRole]:
        """Get a specific user-role link."""
        result = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_user_role(
        self, session: AsyncSession, user_id: UUID, role_id: UUID
    ) -> None:
        """Insert a user-role link. Does NOT commit."""
        session.add(UserRole(user_id=user_id, role_id=role_id))
        await session.flush()

    async def remove_user_role(
        self, session: AsyncSession, user_role: UserRole
    ) -> None:
        """Delete a user-role link. Does NOT commit."""
        await session.delete(user_role)
        await session.flush()


role_crud = RoleCRUD()
