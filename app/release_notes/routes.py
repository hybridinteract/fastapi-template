"""
Release Notes API Endpoints.

Public (authenticated):
- GET /release-notes/latest   — Latest published note
- GET /release-notes           — All published notes (paginated)

Admin only (is_superuser):
- GET /release-notes/all       — All notes including drafts
- POST /release-notes          — Create draft
- PUT /release-notes/{id}      — Update
- DELETE /release-notes/{id}   — Hard delete
- PATCH /release-notes/{id}/publish — Toggle publish/unpublish
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.user.auth_management.utils import get_current_user_validated
from app.user.models import User
from .schemas import (
    ReleaseNoteCreate,
    ReleaseNoteUpdate,
    ReleaseNoteResponse,
    ReleaseNoteListResponse,
)
from .service import release_note_service

logger = get_logger(__name__)

router = APIRouter(prefix="/release-notes", tags=["Release Notes"])


# ==================== HELPERS ====================


def _require_superuser(user: User) -> None:
    """Raise 403 if user is not a superuser."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )


# ==================== PUBLIC ENDPOINTS (authenticated) ====================


@router.get(
    "/latest",
    response_model=ReleaseNoteResponse | None,
    summary="Get latest published release note",
)
async def get_latest_release_note(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Returns the most recently published release note.
    Returns null if no published notes exist.

    Used by the frontend to check if there's a new release to show.
    """
    note = await release_note_service.get_latest_published(session)
    if not note:
        return None
    return ReleaseNoteResponse.model_validate(note)


@router.get(
    "",
    response_model=ReleaseNoteListResponse,
    summary="List published release notes",
)
async def list_published_release_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Retrieve a paginated list of published release notes.
    Ordered by published_at descending (newest first).
    """
    items, total = await release_note_service.get_published_list(
        session, skip=skip, limit=limit,
    )
    return ReleaseNoteListResponse(
        items=[ReleaseNoteResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


# ==================== ADMIN ENDPOINTS (super_admin only) ====================


@router.get(
    "/all",
    response_model=ReleaseNoteListResponse,
    summary="List all release notes (admin)",
)
async def list_all_release_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Retrieve all release notes including drafts.
    **Super admin only.**
    """
    _require_superuser(current_user)

    items, total = await release_note_service.get_all_list(
        session, skip=skip, limit=limit,
    )
    return ReleaseNoteListResponse(
        items=[ReleaseNoteResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=ReleaseNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create release note (admin)",
)
async def create_release_note(
    data: ReleaseNoteCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Create a new release note as a draft.
    **Super admin only.**

    ## Request Body
    | Field | Type | Required | Notes |
    |---|---|---|---|
    | `version` | string | ✅ | Unique version label, 1–50 chars |
    | `title` | string | ✅ | Title, 1–255 chars |
    | `content_md` | string | ✅ | Markdown body |
    | `change_type` | string | No | Default: `feature` |
    """
    _require_superuser(current_user)

    note = await release_note_service.create_note(session, data, current_user.id)
    return ReleaseNoteResponse.model_validate(note)


@router.put(
    "/{note_id}",
    response_model=ReleaseNoteResponse,
    summary="Update release note (admin)",
)
async def update_release_note(
    data: ReleaseNoteUpdate,
    note_id: UUID = Path(..., description="Release note UUID"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Update an existing release note.
    **Super admin only.**
    """
    _require_superuser(current_user)

    note = await release_note_service.update_note(session, note_id, data)
    return ReleaseNoteResponse.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete release note (admin)",
)
async def delete_release_note(
    note_id: UUID = Path(..., description="Release note UUID"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Delete a release note permanently.
    **Super admin only.**
    """
    _require_superuser(current_user)

    await release_note_service.delete_note(session, note_id)


@router.patch(
    "/{note_id}/publish",
    response_model=ReleaseNoteResponse,
    summary="Toggle publish status (admin)",
)
async def toggle_publish_release_note(
    note_id: UUID = Path(..., description="Release note UUID"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_validated),
):
    """
    Toggle a release note between published and draft.
    Sets `published_at` when publishing, clears it when unpublishing.
    **Super admin only.**
    """
    _require_superuser(current_user)

    note = await release_note_service.toggle_publish(session, note_id)
    return ReleaseNoteResponse.model_validate(note)
