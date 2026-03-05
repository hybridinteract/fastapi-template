"""
User Pydantic schemas.

Auth-related schemas: registration, login, token handling, basic user responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.user.models import UserStatus


# ==================== BASE SCHEMAS ====================

class UserBase(BaseModel):
    """Base user schema."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user with email/password."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


# ==================== UPDATE SCHEMAS ====================

class UserUpdateSelf(BaseModel):
    """Schema for users updating their own profile (restricted fields)."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


# ==================== RESPONSE SCHEMAS ====================

class UserResponse(BaseModel):
    """User response schema."""
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
    """Minimal user schema for nested responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: Optional[str] = None
    full_name: Optional[str] = None


# ==================== TOKEN SCHEMAS ====================

class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Token refresh request schema."""
    refresh_token: str


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    exp: datetime
    type: str  # "access" or "refresh"


class ChangePasswordRequest(BaseModel):
    """Schema for changing user password."""
    current_password: str
    new_password: str = Field(..., min_length=8)
