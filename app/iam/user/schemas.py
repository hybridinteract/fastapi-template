"""User management Pydantic schemas — user self-service and admin operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.iam.enums import UserStatus

# ==================== USER BASE ====================


class UserBase(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    department: str | None = None


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=8)


class UserUpdateSelf(BaseModel):
    """Fields users may update on their own profile."""

    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    department: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    department: str | None = None
    is_active: bool | None = None


# ==================== USER RESPONSE ====================


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    department: str | None = None
    status: UserStatus
    email_verified: bool
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserMinimal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None = None
    full_name: str | None = None


class UserOption(BaseModel):
    """A user as a picker shows them: no contact details, nothing about their access."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    avatar_url: str | None = None


# ==================== ADMIN CREATE / UPDATE ====================


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    phone: str | None = None


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    status: UserStatus | None = None


# ==================== ROLE ====================
# RoleResponse is the user-facing role shape, embedded in UserWithRolesResponse.
# The permission-bearing variant (RoleWithPermissions) and the permission catalog
# schemas live in app.iam.permission.schemas.


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    is_system: bool
    created_at: datetime


# ==================== ROLE ASSIGNMENT ====================


class AssignRoleRequest(BaseModel):
    role_ids: list[UUID]


# ==================== USER WITH ROLES ====================


class UserWithRolesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    department: str | None = None
    status: UserStatus
    email_verified: bool
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    roles: list[RoleResponse] = []


# ==================== PAGINATION ====================


class UserListResponse(BaseModel):
    items: list[UserWithRolesResponse]
    total: int
    skip: int
    limit: int
