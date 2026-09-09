"""User management Pydantic schemas — user self-service and admin operations."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.iam.enums import UserStatus


# ==================== USER BASE ====================

class UserBase(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=8)


class UserUpdateSelf(BaseModel):
    """Fields users may update on their own profile."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


# ==================== USER RESPONSE ====================

class UserResponse(BaseModel):
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


class UserMinimal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: Optional[str] = None
    full_name: Optional[str] = None


# ==================== ADMIN CREATE / UPDATE ====================

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    phone: Optional[str] = None


class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[UserStatus] = None


# ==================== ROLE ====================
# RoleResponse is the user-facing role shape, embedded in UserWithRolesResponse.
# The permission-bearing variant (RoleWithPermissions) and the permission catalog
# schemas live in app.iam.permission.schemas.

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime


# ==================== ROLE ASSIGNMENT ====================

class AssignRoleRequest(BaseModel):
    role_ids: List[UUID]


# ==================== USER WITH ROLES ====================

class UserWithRolesResponse(BaseModel):
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
    items: List[UserWithRolesResponse]
    total: int
    skip: int
    limit: int
