"""
User CRUD operations.
"""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.crud import CRUDBase
from app.core.utils import utc_now
from app.user.models import User, UserStatus, Role
from app.user.schemas import UserCreate, UserUpdate


class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for User model."""

    def __init__(self):
        super().__init__(User)

    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[User]:
        """Get active (non-deleted) user by email."""
        query = select(self.model).where(
            self.model.email == email,
            self.model.is_deleted == False,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_phone(self, session: AsyncSession, phone: str) -> Optional[User]:
        """Get active (non-deleted) user by phone."""
        query = select(self.model).where(
            self.model.phone == phone,
            self.model.is_deleted == False,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def create_with_password(
        self,
        session: AsyncSession,
        *,
        obj_in: UserCreate,
        hashed_password: str,
    ) -> User:
        """Create a new user with a hashed password.

        Excludes the plain 'password' field and sets 'hashed_password' instead.
        Does NOT commit — service layer owns the transaction.
        """
        obj_data = obj_in.model_dump(exclude={"password"})
        db_obj = self.model(**obj_data, hashed_password=hashed_password)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def soft_delete(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        deleted_by: Optional[UUID] = None,
    ) -> Optional[User]:
        """Soft-delete a user by setting is_deleted and deleted_at.

        Does NOT commit — service layer owns the transaction.
        """
        user = await self.get(session, user_id)
        if not user or user.is_deleted:
            return None
        user.is_deleted = True
        user.deleted_at = utc_now()
        user.deleted_by_user_id = deleted_by
        user.is_active = False
        await session.flush()
        await session.refresh(user)
        return user

    # ── Admin queries (pagination & filtering) ───────────────────

    async def get_user_with_roles(
        self, session: AsyncSession, user_id: UUID
    ) -> Optional[User]:
        """Get a single non-deleted user with roles eagerly loaded."""
        result = await session.execute(
            select(self.model)
            .where(self.model.id == user_id, self.model.is_deleted == False)
            .options(selectinload(self.model.roles))
        )
        return result.scalar_one_or_none()

    async def get_users_with_roles_by_ids(
        self, session: AsyncSession, user_ids: List[UUID]
    ) -> List[User]:
        """Get multiple non-deleted users with roles eagerly loaded."""
        if not user_ids:
            return []
        result = await session.execute(
            select(self.model)
            .where(self.model.id.in_(user_ids), self.model.is_deleted == False)
            .options(selectinload(self.model.roles))
        )
        return list(result.scalars().all())

    async def list_users_paginated(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        role: Optional[str] = None,
        status: Optional[UserStatus] = None,
        search: Optional[str] = None,
    ) -> tuple[List[User], int]:
        """Return (users, total_count) with filters and pagination."""
        query = (
            select(self.model)
            .where(self.model.is_deleted == False)
            .options(selectinload(self.model.roles))
        )

        if role:
            query = query.join(self.model.roles).where(Role.name == role)
        if status:
            query = query.where(self.model.status == status)
        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    self.model.full_name.ilike(term),
                    self.model.email.ilike(term),
                    self.model.phone.ilike(term),
                )
            )

        # Total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginated results
        query = query.order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        users = list(result.scalars().unique().all())

        return users, total

    async def list_deleted_users_paginated(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[List[User], int]:
        """Return (deleted_users, total_count) with filters and pagination."""
        query = (
            select(self.model)
            .where(self.model.is_deleted == True)
            .options(selectinload(self.model.roles))
        )

        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    self.model.full_name.ilike(term),
                    self.model.email.ilike(term),
                    self.model.phone.ilike(term),
                )
            )

        # Total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginated results
        query = query.order_by(self.model.deleted_at.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        users = list(result.scalars().unique().all())

        return users, total


user_crud = UserCRUD()
