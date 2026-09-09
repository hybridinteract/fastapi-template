"""Core auth routes: token refresh, logout, /me — provider-agnostic."""

from fastapi import APIRouter

from app.core.database import SessionDep
from app.user.auth.schemas import (
    LogoutRequest,
    MeResponse,
    TokenRefresh,
    TokenResponse,
)
from app.user.dependencies import (
    CurrentUserDep,
    TokenServiceDep,
    UserServiceDep,
)

router = APIRouter(tags=["Auth: Core"])


@router.post("/refresh")
async def refresh_token_endpoint(
    data: TokenRefresh,
    session: SessionDep,
    token_service: TokenServiceDep,
) -> TokenResponse:
    """Rotate access token using a valid refresh token."""
    return await token_service.refresh_token(session, data.refresh_token)


@router.post("/logout")
async def logout(
    data: LogoutRequest,
    session: SessionDep,
    token_service: TokenServiceDep,
) -> dict:
    """Revoke the current session's refresh token."""
    if data.refresh_token:
        await token_service.logout(session, data.refresh_token)
    return {"status": "success"}


@router.post("/logout-all")
async def logout_all(
    session: SessionDep,
    current_user: CurrentUserDep,
    token_service: TokenServiceDep,
) -> dict:
    """Revoke all refresh tokens for the current user (logout from all devices)."""
    count = await token_service.logout_all(session, current_user.id)
    return {"status": "success", "revoked_tokens": count}


@router.get("/me")
async def get_me(
    session: SessionDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
) -> MeResponse:
    """Return the authenticated user's profile with flattened roles/permissions."""
    return await user_service.get_me(session, current_user)
