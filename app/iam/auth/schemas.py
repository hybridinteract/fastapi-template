"""Auth-specific Pydantic schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.iam.enums import UserStatus


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the access token expires.")
    user_id: Optional[UUID] = None


class TokenRefresh(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class MeResponse(BaseModel):
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
    role: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    has_password: bool = False
    linked_providers: List[str] = Field(default_factory=list)


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    type: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class GoogleAuthRequest(BaseModel):
    id_token: str
    device_info: Optional[str] = None


class OTPRequestSchema(BaseModel):
    phone: str = Field(description="Phone number in E.164 format (+1234567890)")


class OTPVerifySchema(BaseModel):
    phone: str
    otp: str = Field(min_length=4, max_length=10)
    device_info: Optional[str] = None
