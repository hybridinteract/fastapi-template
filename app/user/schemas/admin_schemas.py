"""
Admin user management schemas.
Used by admin routes for managing users, roles, and permissions.

Follows the project schema pattern: one file for all admin-related schemas,
grouped by purpose with clear section headers.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.user.models import UserStatus


# ==================== ADMIN CREATE / UPDATE ====================

class AdminUserCreate(BaseModel):
    """Schema for admin creating a user (no self-registration)."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    phone: Optional[str] = None


class AdminUserUpdate(BaseModel):
    """Schema for admin updating a user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[UserStatus] = None


# ==================== ROLE & PERMISSION SCHEMAS ====================

class PermissionResponse(BaseModel):
    """Permission response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class RoleResponse(BaseModel):
    """Role response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime


class RoleWithPermissions(RoleResponse):
    """Role response with permissions included."""
    permissions: List[PermissionResponse] = []


# ==================== ROLE ASSIGNMENT ====================

class AssignRoleRequest(BaseModel):
    """Request to assign a single role to a user.
    Each user has exactly one role - assigns the given role
    (replaces if user already has a different role).
    """
    role_ids: List[UUID]


class UpdateRolePermissionsRequest(BaseModel):
    """Request to set permissions for a role (replaces all current permissions)."""
    permission_ids: List[UUID]


# ==================== USER RESPONSE WITH ROLES ====================

class UserWithRolesResponse(BaseModel):
    """Extended user response including roles."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    status: UserStatus
    email_verified: bool
    is_active: bool
    is_superuser: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleResponse] = []


# ==================== PAGINATION ====================

class UserListResponse(BaseModel):
    """User list response with skip/limit pagination."""
    items: List[UserWithRolesResponse]
    total: int
    skip: int
    limit: int
