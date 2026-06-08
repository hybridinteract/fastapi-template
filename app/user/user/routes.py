"""User management routes — self-service and admin endpoints.

Routes call services via Annotated Dep aliases (conventions §4 + §5).
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.database import SessionDep
from app.user.dependencies import (
    AdminServiceDep,
    CurrentUserDep,
    SuperUserDep,
    UserQueryServiceDep,
    UserServiceDep,
)
from app.user.enums import UserStatus
from app.user.user.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    AssignRoleRequest,
    UserListResponse,
    UserResponse,
    UserUpdateSelf,
    UserWithRolesResponse,
)

user_router = APIRouter(prefix="/users/me", tags=["users"])
admin_router = APIRouter(prefix="/users", tags=["User Management"])


# ── Self-service routes ───────────────────────────────────────────────────────

@user_router.get("")
async def get_my_profile(
    session: SessionDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
) -> UserResponse:
    """Get current user's profile."""
    return await user_service.get_my_profile(session, current_user.id)


@user_router.patch("")
async def update_my_profile(
    update_data: UserUpdateSelf,
    session: SessionDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
) -> UserResponse:
    """Update current user's own profile (restricted fields only)."""
    return await user_service.update_my_profile(session, current_user.id, update_data)


@user_router.get("/by-role/{role}")
async def get_users_by_role(
    role: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    query_service: UserQueryServiceDep,
) -> list[UserResponse]:
    """Get all active users for a given role name (served from cache when warm)."""
    return await query_service.get_active_users_by_role(session, role)


# ── Admin collection routes ───────────────────────────────────────────────────

@admin_router.get("", summary="List all users")
async def list_users(
    session: SessionDep,
    _: SuperUserDep,
    admin_service: AdminServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    role: Annotated[Optional[str], Query(description="Filter by role name")] = None,
    status_filter: Annotated[Optional[UserStatus], Query(alias="status")] = None,
    search: Annotated[Optional[str], Query(description="Search by name, email, or phone")] = None,
) -> UserListResponse:
    return await admin_service.list_users(
        session,
        skip=skip,
        limit=limit,
        role=role,
        status_filter=status_filter,
        search=search,
    )


@admin_router.post("", status_code=status.HTTP_201_CREATED, summary="Create a new user")
async def create_user(
    user_data: AdminUserCreate,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> UserWithRolesResponse:
    return await admin_service.create_user(session, user_data, current_user)


# ── Admin meta routes (before /{user_id}) ─────────────────────────────────────

@admin_router.get("/deleted", summary="List deleted users")
async def list_deleted_users(
    session: SessionDep,
    _: SuperUserDep,
    admin_service: AdminServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    search: Annotated[Optional[str], Query()] = None,
) -> UserListResponse:
    return await admin_service.list_deleted_users(
        session, skip=skip, limit=limit, search=search
    )


# RBAC catalog endpoints (list roles/permissions, set role permissions) moved to
# app.user.permission_management.routes (rbac_router), same /users/meta/* paths.


# ── Admin user detail routes ──────────────────────────────────────────────────

@admin_router.get("/{user_id}", summary="Get user details")
async def get_user(
    user_id: UUID,
    session: SessionDep,
    _: SuperUserDep,
    admin_service: AdminServiceDep,
) -> UserWithRolesResponse:
    return await admin_service.get_user(session, user_id)


@admin_router.patch("/{user_id}", summary="Update user")
async def update_user(
    user_id: UUID,
    updates: AdminUserUpdate,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> UserWithRolesResponse:
    return await admin_service.update_user(session, user_id, updates, current_user)


@admin_router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete user"
)
async def delete_user(
    user_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> None:
    await admin_service.delete_user(session, user_id, current_user)


@admin_router.post("/{user_id}/restore", summary="Restore deleted user")
async def restore_user(
    user_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> UserWithRolesResponse:
    return await admin_service.restore_user(session, user_id, current_user)


@admin_router.delete(
    "/{user_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete user",
)
async def hard_delete_user(
    user_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> None:
    await admin_service.hard_delete_user(session, user_id, current_user)


# ── Role assignment ───────────────────────────────────────────────────────────

@admin_router.post("/{user_id}/roles", summary="Assign roles to user")
async def assign_roles(
    user_id: UUID,
    body: AssignRoleRequest,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> UserWithRolesResponse:
    return await admin_service.assign_roles(
        session, user_id, body.role_ids, current_user
    )


@admin_router.delete("/{user_id}/roles/{role_id}", summary="Remove role from user")
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
    admin_service: AdminServiceDep,
) -> UserWithRolesResponse:
    return await admin_service.remove_role(session, user_id, role_id, current_user)
