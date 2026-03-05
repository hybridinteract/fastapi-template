"""
Release Note database model.

Stores release notes / "What's New" announcements.
Single flat table — follows industry standard (GitHub, Linear, Notion).

Timezone Standards:
- All datetime fields use UTC timezone (timezone=True in DateTime columns)
- Frontend handles timezone conversion for display
"""

from datetime import datetime
from uuid import uuid4, UUID as UUIDType
from typing import Optional
from enum import Enum

from sqlalchemy import String, DateTime, Boolean, Text, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base
from app.core.utils import utc_now


class ChangeType(str, Enum):
    """Type of change in this release note."""
    FEATURE = "feature"
    IMPROVEMENT = "improvement"
    BUGFIX = "bugfix"
    BREAKING = "breaking"


class ReleaseNote(Base):
    """Release note model for 'What's New' announcements."""

    __tablename__ = "release_notes"
    __table_args__ = (
        Index('ix_release_notes_published', 'is_published', 'published_at'),
        Index('ix_release_notes_version', 'version'),
    )

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    version: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    content_md: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    change_type: Mapped[ChangeType] = mapped_column(
        SQLEnum(ChangeType, values_callable=lambda x: [e.value for e in x]),
        default=ChangeType.FEATURE,
        nullable=False
    )

    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )
    created_by: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationship to User (optional, for display)
    author = relationship("User", foreign_keys=[created_by], lazy="noload")

    def __repr__(self) -> str:
        return f"<ReleaseNote(id={self.id}, version={self.version}, published={self.is_published})>"
