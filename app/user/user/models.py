"""User-domain database models — user account and user-role assignment.

Timezone Standards:
- All datetime fields use UTC timezone (timezone=True in DateTime columns)
- Frontend handles timezone conversion for display
- Apply same pattern to all future models requiring datetime fields
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base
from app.core.utils import utc_now
from app.user.enums import UserStatus


class User(Base):
    """User model with email/password authentication and profile fields."""

    __tablename__ = "users"
    __table_args__ = (
        Index('ix_users_status', 'status'),
        Index('ix_users_phone', 'phone'),
        Index('ix_users_department', 'department'),
        Index('ix_users_is_deleted', 'is_deleted'),
    )

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Email authentication (nullable to support phone-only OTP accounts)
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Basic details
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus, values_callable=lambda x: [e.value for e in x]),
        default=UserStatus.ACTIVE,
        nullable=False
    )

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Timestamps
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

    # Optional profile fields
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    department: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # Audit fields
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    deleted_by_user_id: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    roles: Mapped[List["Role"]] = relationship(  # noqa: F821
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(  # noqa: F821
        "RefreshToken",
        back_populates="user",
        lazy="noload",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class UserRole(Base):
    """Association table for User-Role."""

    __tablename__ = "user_roles"

    user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    role_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
