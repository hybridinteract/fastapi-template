"""
Release Note Pydantic schemas.

Request and response schemas for release note operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ==================== REQUEST SCHEMAS ====================


class ReleaseNoteCreate(BaseModel):
    """Schema for creating a new release note."""
    version: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Version label (e.g., '1.5.0', 'Feb 2026 Update')",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Release note title",
    )
    content_md: str = Field(
        ...,
        min_length=1,
        description="Markdown body of the release note",
    )
    change_type: str = Field(
        "feature",
        description="Type of change: feature, improvement, bugfix, breaking",
    )


class ReleaseNoteUpdate(BaseModel):
    """Schema for updating an existing release note (partial update)."""
    version: Optional[str] = Field(None, min_length=1, max_length=50)
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content_md: Optional[str] = Field(None, min_length=1)
    change_type: Optional[str] = None


# ==================== RESPONSE SCHEMAS ====================


class ReleaseNoteAuthor(BaseModel):
    """Minimal author info for release note response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: Optional[str] = None


class ReleaseNoteResponse(BaseModel):
    """Full release note response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: str
    title: str
    content_md: str
    change_type: str
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    author: Optional[ReleaseNoteAuthor] = None


class ReleaseNoteListResponse(BaseModel):
    """Paginated release note list response."""
    items: List[ReleaseNoteResponse]
    total: int
    skip: int
    limit: int
