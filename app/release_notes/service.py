"""
Release Note Service - Business Logic Layer.

Orchestrates business operations for release notes, enforces rules, controls transactions.
CRUD operations do NOT commit — service calls session.commit().
"""

from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.utils import utc_now
from .models import ReleaseNote
from .schemas import ReleaseNoteCreate, ReleaseNoteUpdate
from .crud import ReleaseNoteCRUD, release_note_crud

logger = get_logger(__name__)


class ReleaseNoteService:
    """Service layer for release note business logic."""

    def __init__(self, crud: ReleaseNoteCRUD):
        self._crud = crud

    # ==================== READ OPERATIONS ====================

    async def get_note_by_id(
        self,
        session: AsyncSession,
        note_id: UUID,
    ) -> ReleaseNote:
        """Get a single release note by ID. Raises 404 if not found."""
        note = await self._crud.get_by_id(session, note_id)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Release note not found",
            )
        return note

    async def get_latest_published(
        self,
        session: AsyncSession,
    ) -> Optional[ReleaseNote]:
        """Get the most recently published release note. Returns None if none exist."""
        return await self._crud.get_latest_published(session)

    async def get_published_list(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ReleaseNote], int]:
        """Get published release notes (for all authenticated users)."""
        return await self._crud.get_published_list(session, skip=skip, limit=limit)

    async def get_all_list(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ReleaseNote], int]:
        """Get all release notes including drafts (admin only)."""
        return await self._crud.get_all_list(session, skip=skip, limit=limit)

    # ==================== CREATE ====================

    async def create_note(
        self,
        session: AsyncSession,
        data: ReleaseNoteCreate,
        current_user_id: UUID,
    ) -> ReleaseNote:
        """Create a new release note (draft). Commits the transaction."""
        # Check for duplicate version
        existing = await self._crud.get_by_version(session, data.version)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Release note with version '{data.version}' already exists",
            )

        note = await self._crud.create_note(
            session, obj_in=data, created_by=current_user_id,
        )

        await session.commit()
        await session.refresh(note)

        logger.info(f"Release note created: v{note.version} by user {current_user_id}")
        return note

    # ==================== UPDATE ====================

    async def update_note(
        self,
        session: AsyncSession,
        note_id: UUID,
        data: ReleaseNoteUpdate,
    ) -> ReleaseNote:
        """Update an existing release note. Commits the transaction."""
        note = await self.get_note_by_id(session, note_id)

        # If version is being changed, check for duplicates
        if data.version and data.version != note.version:
            existing = await self._crud.get_by_version(session, data.version)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Release note with version '{data.version}' already exists",
                )

        updated = await self._crud.update_note(session, db_obj=note, obj_in=data)
        await session.commit()
        await session.refresh(updated)

        logger.info(f"Release note updated: v{updated.version}")
        return updated

    # ==================== DELETE ====================

    async def delete_note(
        self,
        session: AsyncSession,
        note_id: UUID,
    ) -> None:
        """Delete a release note. Commits the transaction."""
        note = await self.get_note_by_id(session, note_id)
        version = note.version
        await self._crud.delete_note(session, note)
        await session.commit()

        logger.info(f"Release note deleted: v{version}")

    # ==================== PUBLISH / UNPUBLISH ====================

    async def toggle_publish(
        self,
        session: AsyncSession,
        note_id: UUID,
    ) -> ReleaseNote:
        """Toggle publish status. Sets published_at when publishing. Commits."""
        note = await self.get_note_by_id(session, note_id)

        if note.is_published:
            # Unpublish
            note.is_published = False
            note.published_at = None
            logger.info(f"Release note unpublished: v{note.version}")
        else:
            # Publish
            note.is_published = True
            note.published_at = utc_now()
            logger.info(f"Release note published: v{note.version}")

        await session.flush()
        await session.commit()
        await session.refresh(note)

        return note


# Singleton instance
release_note_service = ReleaseNoteService(crud=release_note_crud)
