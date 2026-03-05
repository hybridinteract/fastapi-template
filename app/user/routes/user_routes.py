"""
User self-service routes.

Endpoints for users to manage their own profiles and query users by role.

Role-Based User Query:
    GET /users/me/by-role/{role}
        Returns all active users for the given role name.
        Roles are dynamic — any role that exists in the database can be queried.
        Restrict access by permission as needed.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.user.models import User
from app.user.services.user_service import user_service
from app.user.schemas.user_schemas import UserResponse, UserUpdateSelf
from app.user.auth_management.utils import get_current_user

router = APIRouter(prefix="/users/me", tags=["users"])


# ==================== PROFILE ENDPOINTS ====================


@router.get("", response_model=UserResponse)
async def get_my_profile(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current user's profile."""
    return await user_service.get_my_profile(session, current_user.id)


@router.patch("", response_model=UserResponse)
async def update_my_profile(
    update_data: UserUpdateSelf,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update current user's own profile (restricted fields only)."""
    return await user_service.update_my_profile(session, current_user.id, update_data)


# ==================== ROLE-BASED USER QUERIES ====================


@router.get("/by-role/{role}", response_model=list[UserResponse])
async def get_users_by_role(
    role: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get all active users for a given role name.

    The `role` path parameter is a free-form string matching a role name in
    the database (e.g. `admin`, `member`, or any project-specific role).
    Uses cached UserQueryService — results are served from Redis when available.

    Example:
        GET /users/me/by-role/admin
        GET /users/me/by-role/member
    """
    from app.user.services.user_query_service import user_query_service

    users = await user_query_service.get_active_users_by_role(session, role)
    return [UserResponse.model_validate(u) for u in users]
