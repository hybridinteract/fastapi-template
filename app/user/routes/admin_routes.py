"""
Admin user management routes.

Thin route layer: request validation → service call → response.
All business logic lives in AdminService.
All routes require super_admin via get_current_active_superuser dependency.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionDep
from app.user.auth_management.utils import SuperUserDep
from app.user.models import UserStatus
from app.user.schemas.admin_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    AssignRoleRequest,
    PermissionResponse,
    RoleWithPermissions,
    UpdateRolePermissionsRequest,
    UserListResponse,
    UserWithRolesResponse,
)
from app.user.services.admin_service import AdminService

router = APIRouter(prefix="/users", tags=["User Management"])


# ── Collection routes ───────────────────────────────────────────────────────


@router.get("", summary="List all users")
async def list_users(
    session: SessionDep,
    _: SuperUserDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    role: Annotated[str | None, Query(description="Filter by role name")] = None,
    status_filter: Annotated[UserStatus | None, Query(alias="status", description="Filter by status")] = None,
    search: Annotated[str | None, Query(description="Search by name, email, or phone")] = None,
) -> UserListResponse:
    """List all users with optional filters and pagination."""
    return await AdminService.list_users(
        session,
        skip=skip,
        limit=limit,
        role=role,
        status_filter=status_filter,
        search=search,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a new user")
async def create_user(
    user_data: AdminUserCreate,
    session: SessionDep,
    current_user: SuperUserDep,
) -> UserWithRolesResponse:
    """Admin creates a new user account."""
    return await AdminService.create_user(session, user_data, current_user)


# ── Meta routes (before /{user_id} to avoid path conflicts) ────────────────


@router.get("/deleted", summary="List deleted users")
async def list_deleted_users(
    session: SessionDep,
    _: SuperUserDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    search: Annotated[str | None, Query(description="Search by name, email, or phone")] = None,
) -> UserListResponse:
    """List all soft-deleted users with pagination."""
    return await AdminService.list_deleted_users(session, skip=skip, limit=limit, search=search)


@router.get("/meta/roles", summary="List all roles")
async def list_roles(
    session: SessionDep,
    _: SuperUserDep,
) -> list[RoleWithPermissions]:
    """List all available roles with their permissions."""
    return await AdminService.list_roles(session)


@router.get("/meta/permissions", summary="List all permissions")
async def list_permissions(
    session: SessionDep,
    _: SuperUserDep,
) -> list[PermissionResponse]:
    """List all available permissions."""
    return await AdminService.list_permissions(session)


@router.put("/meta/roles/{role_id}/permissions", summary="Set role permissions")
async def set_role_permissions(
    role_id: UUID,
    body: UpdateRolePermissionsRequest,
    session: SessionDep,
    current_user: SuperUserDep,
) -> RoleWithPermissions:
    """Replace all permissions for a role with the given set."""
    return await AdminService.set_role_permissions(session, role_id, body.permission_ids, current_user)


# ── User detail routes ──────────────────────────────────────────────────────


@router.get("/{user_id}", summary="Get user details")
async def get_user(
    user_id: UUID,
    session: SessionDep,
    _: SuperUserDep,
) -> UserWithRolesResponse:
    """Get detailed user info by ID including roles."""
    return await AdminService.get_user(session, user_id)


@router.patch("/{user_id}", summary="Update user")
async def update_user(
    user_id: UUID,
    updates: AdminUserUpdate,
    session: SessionDep,
    current_user: SuperUserDep,
) -> UserWithRolesResponse:
    """Admin updates user profile."""
    return await AdminService.update_user(session, user_id, updates, current_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete user")
async def delete_user(
    user_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
) -> None:
    """Soft-delete a user."""
    await AdminService.delete_user(session, user_id, current_user)


@router.post("/{user_id}/restore", summary="Restore deleted user")
async def restore_user(
    user_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
) -> UserWithRolesResponse:
    """Restore a soft-deleted user."""
    return await AdminService.restore_user(session, user_id, current_user)


@router.delete("/{user_id}/permanent", status_code=status.HTTP_204_NO_CONTENT, summary="Permanently delete user")
async def hard_delete_user(
    user_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
) -> None:
    """Permanently delete a user from the database. This action cannot be undone."""
    await AdminService.hard_delete_user(session, user_id, current_user)


# ── Role assignment ─────────────────────────────────────────────────────────


@router.post("/{user_id}/roles", summary="Assign roles to user")
async def assign_roles(
    user_id: UUID,
    body: AssignRoleRequest,
    session: SessionDep,
    current_user: SuperUserDep,
) -> UserWithRolesResponse:
    """Assign one or more roles to a user."""
    return await AdminService.assign_roles(session, user_id, body.role_ids, current_user)


@router.delete("/{user_id}/roles/{role_id}", summary="Remove role from user")
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    session: SessionDep,
    current_user: SuperUserDep,
) -> UserWithRolesResponse:
    """Remove a specific role from a user."""
    return await AdminService.remove_role(session, user_id, role_id, current_user)
