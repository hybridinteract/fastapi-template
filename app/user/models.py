"""
User database models.

Timezone Standards:
- All datetime fields use UTC timezone (timezone=True in DateTime columns)
- Frontend handles timezone conversion for display
- Apply same pattern to all future models requiring datetime fields
"""

from datetime import datetime
from uuid import uuid4, UUID as UUIDType
from typing import Optional, List
from enum import Enum

from sqlalchemy import String, DateTime, Boolean, Text, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base
from app.core.utils import utc_now


class UserStatus(str, Enum):
    """Enum for user account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


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
    
    # Email authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
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
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        lazy="noload",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class RefreshToken(Base):
    """Refresh token model for session management and device tracking."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index('ix_refresh_tokens_user', 'user_id'),
        Index('ix_refresh_tokens_expires', 'expires_at'),
    )

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    device_info: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"


class Permission(Base):
    """Permission model for RBAC."""

    __tablename__ = "permissions"
    __table_args__ = (
        Index('ix_permissions_resource_action', 'resource', 'action'),
    )

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="noload"
    )


class Role(Base):
    """Role model for RBAC."""

    __tablename__ = "roles"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

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

    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin"
    )
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="noload"
    )


class RolePermission(Base):
    """Association table for Role-Permission."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True
    )
    permission_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )


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
