"""
User self-service routes.

Endpoints for users to manage their own profiles and query users by role.

Role-Based User Query:
    GET /users/me/by-role/{role}
        Returns all active users for the given role name.
        Roles are dynamic — any role that exists in the database can be queried.
        Restrict access by permission as needed.
"""

from fastapi import APIRouter

from app.core.database import SessionDep
from app.user.auth_management.utils import CurrentUserDep
from app.user.schemas.user_schemas import UserResponse, UserUpdateSelf
from app.user.services.user_service import user_service

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("")
async def get_my_profile(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> UserResponse:
    """Get current user's profile."""
    return await user_service.get_my_profile(session, current_user.id)


@router.patch("")
async def update_my_profile(
    update_data: UserUpdateSelf,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> UserResponse:
    """Update current user's own profile (restricted fields only)."""
    return await user_service.update_my_profile(session, current_user.id, update_data)


@router.get("/by-role/{role}")
async def get_users_by_role(
    role: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[UserResponse]:
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
