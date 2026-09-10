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

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from app.core.database import SessionDep
from app.iam import CurrentUserDep, SuperUserDep
from .dependencies import ReleaseNoteServiceDep
from .schemas import (
    ReleaseNoteCreate,
    ReleaseNoteListResponse,
    ReleaseNoteResponse,
    ReleaseNoteUpdate,
)

router = APIRouter(prefix="/release-notes", tags=["Release Notes"])


# ── Public (authenticated) ──────────────────────────────────────────────────


@router.get("/latest", summary="Get latest published release note")
async def get_latest_release_note(
    session: SessionDep,
    _: CurrentUserDep,
    service: ReleaseNoteServiceDep,
) -> ReleaseNoteResponse | None:
    """
    Returns the most recently published release note.
    Returns null if no published notes exist.

    Used by the frontend to check if there's a new release to show.
    """
    note = await service.get_latest_published(session)
    if not note:
        return None
    return ReleaseNoteResponse.model_validate(note)


@router.get("", summary="List published release notes")
async def list_published_release_notes(
    session: SessionDep,
    _: CurrentUserDep,
    service: ReleaseNoteServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReleaseNoteListResponse:
    """
    Retrieve a paginated list of published release notes.
    Ordered by published_at descending (newest first).
    """
    items, total = await service.get_published_list(session, skip=skip, limit=limit)
    return ReleaseNoteListResponse(
        items=[ReleaseNoteResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


# ── Admin (developer_admin only) ────────────────────────────────────────────────


@router.get("/all", summary="List all release notes (admin)")
async def list_all_release_notes(
    session: SessionDep,
    _: SuperUserDep,
    service: ReleaseNoteServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReleaseNoteListResponse:
    """
    Retrieve all release notes including drafts.
    **Super admin only.**
    """
    items, total = await service.get_all_list(session, skip=skip, limit=limit)
    return ReleaseNoteListResponse(
        items=[ReleaseNoteResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create release note (admin)")
async def create_release_note(
    data: ReleaseNoteCreate,
    session: SessionDep,
    current_user: SuperUserDep,
    service: ReleaseNoteServiceDep,
) -> ReleaseNoteResponse:
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
    note = await service.create_note(session, data, current_user.id)
    return ReleaseNoteResponse.model_validate(note)


@router.put("/{note_id}", summary="Update release note (admin)")
async def update_release_note(
    data: ReleaseNoteUpdate,
    session: SessionDep,
    _: SuperUserDep,
    service: ReleaseNoteServiceDep,
    note_id: Annotated[UUID, Path(description="Release note UUID")],
) -> ReleaseNoteResponse:
    """
    Update an existing release note.
    **Super admin only.**
    """
    note = await service.update_note(session, note_id, data)
    return ReleaseNoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete release note (admin)")
async def delete_release_note(
    session: SessionDep,
    _: SuperUserDep,
    service: ReleaseNoteServiceDep,
    note_id: Annotated[UUID, Path(description="Release note UUID")],
) -> None:
    """
    Delete a release note permanently.
    **Super admin only.**
    """
    await service.delete_note(session, note_id)


@router.patch("/{note_id}/publish", summary="Toggle publish status (admin)")
async def toggle_publish_release_note(
    session: SessionDep,
    _: SuperUserDep,
    service: ReleaseNoteServiceDep,
    note_id: Annotated[UUID, Path(description="Release note UUID")],
) -> ReleaseNoteResponse:
    """
    Toggle a release note between published and draft.
    Sets `published_at` when publishing, clears it when unpublishing.
    **Super admin only.**
    """
    note = await service.toggle_publish(session, note_id)
    return ReleaseNoteResponse.model_validate(note)
