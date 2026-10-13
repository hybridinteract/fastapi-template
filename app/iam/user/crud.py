"""User-domain CRUD — User account data access. Never commits.

Role/Permission CRUD lives in ``app.iam.permission.crud``.
"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.crud import CRUDBase
from app.core.utils import escape_like, utc_now
from app.iam.enums import UserStatus
from app.iam.permission.models import Role
from app.iam.user.models import User
from app.iam.user.schemas import UserCreate, UserUpdate

# ── User ──────────────────────────────────────────────────────────────────────


class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(User)

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        result = await session.execute(
            select(User).where(User.email == email, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, session: AsyncSession, phone: str) -> User | None:
        result = await session.execute(
            select(User).where(User.phone == phone, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_user_with_roles(self, session: AsyncSession, user_id) -> User | None:
        result = await session.execute(
            select(User)
            .where(User.id == user_id, User.is_deleted == False)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_users_with_roles_by_ids(
        self, session: AsyncSession, user_ids: list[UUID]
    ) -> list[User]:
        if not user_ids:
            return []
        result = await session.execute(
            select(User)
            .where(User.id.in_(user_ids), User.is_deleted == False)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        return list(result.scalars().unique().all())

    async def create_with_password(
        self,
        session: AsyncSession,
        *,
        obj_in: UserCreate,
        hashed_password: str | None,
    ) -> User:
        obj_data = obj_in.model_dump(exclude={"password"})
        db_obj = User(**obj_data, hashed_password=hashed_password)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def soft_delete(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        deleted_by: UUID | None = None,
    ) -> User | None:
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

    async def list_users_paginated(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        role: str | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        query = select(User).where(User.is_deleted == False).options(selectinload(User.roles))
        if role:
            query = query.join(User.roles).where(Role.name == role)
        if status:
            query = query.where(User.status == status)
        if search:
            term = f"%{escape_like(search)}%"
            query = query.where(
                or_(
                    User.full_name.ilike(term),
                    User.email.ilike(term),
                    User.phone.ilike(term),
                )
            )

        total = (
            await session.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        query = query.order_by(User.created_at.desc(), User.id.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().unique().all()), total

    async def list_deleted_users_paginated(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        query = select(User).where(User.is_deleted == True).options(selectinload(User.roles))
        if search:
            term = f"%{escape_like(search)}%"
            query = query.where(
                or_(
                    User.full_name.ilike(term),
                    User.email.ilike(term),
                    User.phone.ilike(term),
                )
            )

        total = (
            await session.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        query = query.order_by(User.deleted_at.desc(), User.id.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().unique().all()), total


# ── Module-level singleton ────────────────────────────────────────────────────

user_crud = UserCRUD()
