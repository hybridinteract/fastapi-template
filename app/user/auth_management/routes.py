"""
Authentication routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.user.schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    TokenRefresh,
    ChangePasswordRequest,
)
from app.user.schemas import UserWithRolesResponse
from .service import AuthService
from .utils import get_current_user
from ..models import User

logger = get_logger(__name__)

router = APIRouter()


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request headers."""
    # Check X-Forwarded-For header first (for proxied requests)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded.split(",")[0].strip()
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    return None


def get_device_info(request: Request) -> Optional[str]:
    """Extract device info (User-Agent) from request headers."""
    return request.headers.get("User-Agent")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user"
)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user account."""
    return await AuthService.register(session, user_data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login user"
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate user and return access token.

    Accepts OAuth2 form data (username + password).
    The `username` field should contain the user's email.
    """
    credentials = UserLogin(email=form_data.username, password=form_data.password)
    device_info = get_device_info(request)
    ip_address = get_client_ip(request)
    return await AuthService.login(
        session,
        credentials,
        device_info=device_info,
        ip_address=ip_address,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token"
)
async def refresh_token(
    token_data: TokenRefresh,
    session: AsyncSession = Depends(get_session),
):
    """Refresh access token using refresh token."""
    return await AuthService.refresh_token(session, token_data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user"
)
async def logout(
    token_data: TokenRefresh,
    session: AsyncSession = Depends(get_session),
):
    """Logout by revoking the refresh token."""
    await AuthService.logout(session, token_data.refresh_token)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout from all devices"
)
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Logout from all devices by revoking all refresh tokens."""
    await AuthService.logout_all(session, current_user.id)


@router.get(
    "/me",
    response_model=UserWithRolesResponse,
    summary="Get current user"
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user with roles."""
    return current_user


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password"
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change password for authenticated user."""
    await AuthService.change_password(
        session,
        current_user.id,
        request.current_password,
        request.new_password,
    )
    return {"message": "Password changed successfully"}
