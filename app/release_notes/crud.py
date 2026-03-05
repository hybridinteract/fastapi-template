"""
Release Note CRUD operations.

IMPORTANT: CRUD methods do NOT commit transactions.
The service layer owns transaction boundaries.
"""

from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.crud import CRUDBase
from .models import ReleaseNote
from .schemas import ReleaseNoteCreate, ReleaseNoteUpdate


class ReleaseNoteCRUD(CRUDBase[ReleaseNote, ReleaseNoteCreate, ReleaseNoteUpdate]):
    """CRUD operations for ReleaseNote model."""

    def __init__(self):
        super().__init__(ReleaseNote)

    # ==================== READ OPERATIONS ====================

    async def get_by_id(
        self,
        session: AsyncSession,
        note_id,
    ) -> Optional[ReleaseNote]:
        """Get a release note by ID with author loaded."""
        query = (
            select(self.model)
            .where(self.model.id == note_id)
            .options(joinedload(self.model.author))
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_version(
        self,
        session: AsyncSession,
        version: str,
    ) -> Optional[ReleaseNote]:
        """Get a release note by version string."""
        query = select(self.model).where(self.model.version == version)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_published(
        self,
        session: AsyncSession,
    ) -> Optional[ReleaseNote]:
        """Get the most recently published release note."""
        query = (
            select(self.model)
            .where(self.model.is_published == True)
            .order_by(self.model.published_at.desc())
            .limit(1)
            .options(joinedload(self.model.author))
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_published_list(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ReleaseNote], int]:
        """Get published release notes with count (for public listing)."""
        # Count
        count_query = select(func.count(self.model.id)).where(
            self.model.is_published == True
        )
        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        # Items
        items_query = (
            select(self.model)
            .where(self.model.is_published == True)
            .order_by(self.model.published_at.desc())
            .offset(skip)
            .limit(limit)
            .options(joinedload(self.model.author))
        )
        result = await session.execute(items_query)
        items = list(result.scalars().unique().all())

        return items, total

    async def get_all_list(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ReleaseNote], int]:
        """Get all release notes (drafts + published) for admin view."""
        # Count
        count_query = select(func.count(self.model.id))
        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        # Items
        items_query = (
            select(self.model)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .options(joinedload(self.model.author))
        )
        result = await session.execute(items_query)
        items = list(result.scalars().unique().all())

        return items, total

    # ==================== WRITE OPERATIONS ====================

    async def create_note(
        self,
        session: AsyncSession,
        *,
        obj_in: ReleaseNoteCreate,
        created_by,
    ) -> ReleaseNote:
        """Create a new release note. Does NOT commit."""
        obj_data = obj_in.model_dump()
        obj_data["created_by"] = created_by
        db_obj = self.model(**obj_data)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def update_note(
        self,
        session: AsyncSession,
        *,
        db_obj: ReleaseNote,
        obj_in: ReleaseNoteUpdate,
    ) -> ReleaseNote:
        """Update an existing release note. Does NOT commit."""
        update_data = obj_in.model_dump(exclude_unset=True)
        if update_data:
            for field, value in update_data.items():
                setattr(db_obj, field, value)
            await session.flush()
            await session.refresh(db_obj)
        return db_obj

    async def delete_note(
        self,
        session: AsyncSession,
        db_obj: ReleaseNote,
    ) -> None:
        """Hard delete a release note. Does NOT commit."""
        await session.delete(db_obj)
        await session.flush()


# Singleton instance
release_note_crud = ReleaseNoteCRUD()
