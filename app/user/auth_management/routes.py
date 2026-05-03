"""
Authentication routes.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.database import SessionDep
from app.core.logging import get_logger
from app.user.schemas import (
    ChangePasswordRequest,
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserWithRolesResponse,
)
from .service import AuthService
from .utils import CurrentUserDep

logger = get_logger(__name__)

router = APIRouter()


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_device_info(request: Request) -> Optional[str]:
    """Extract device info (User-Agent) from request headers."""
    return request.headers.get("User-Agent")


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register new user")
async def register(
    user_data: UserCreate,
    session: SessionDep,
) -> UserResponse:
    """Register a new user account."""
    return await AuthService.register(session, user_data)


@router.post("/login", summary="Login user")
async def login(
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request = None,
) -> TokenResponse:
    """Authenticate user and return access token.

    Accepts OAuth2 form data (username + password).
    The `username` field should contain the user's email.
    """
    credentials = UserLogin(email=form_data.username, password=form_data.password)
    return await AuthService.login(
        session,
        credentials,
        device_info=get_device_info(request),
        ip_address=get_client_ip(request),
    )


@router.post("/refresh", summary="Refresh access token")
async def refresh_token(
    token_data: TokenRefresh,
    session: SessionDep,
) -> TokenResponse:
    """Refresh access token using refresh token."""
    return await AuthService.refresh_token(session, token_data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Logout user")
async def logout(
    token_data: TokenRefresh,
    session: SessionDep,
) -> None:
    """Logout by revoking the refresh token."""
    await AuthService.logout(session, token_data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, summary="Logout from all devices")
async def logout_all(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    """Logout from all devices by revoking all refresh tokens."""
    await AuthService.logout_all(session, current_user.id)


@router.get("/me", summary="Get current user")
async def get_me(
    current_user: CurrentUserDep,
) -> UserWithRolesResponse:
    """Get current authenticated user with roles."""
    return current_user


@router.post("/change-password", status_code=status.HTTP_200_OK, summary="Change password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, str]:
    """Change password for authenticated user."""
    await AuthService.change_password(
        session,
        current_user.id,
        request.current_password,
        request.new_password,
    )
    return {"message": "Password changed successfully"}
