"""
Admin user management routes.

Thin route layer: request validation → service call → response.
All business logic lives in AdminService.
All routes require super_admin via get_current_active_superuser dependency.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.user.auth_management.utils import get_current_active_superuser
from app.user.models import User, UserStatus
from app.user.schemas.admin_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    UserWithRolesResponse,
    UserListResponse,
    RoleWithPermissions,
    PermissionResponse,
    AssignRoleRequest,
    UpdateRolePermissionsRequest,
)
from app.user.services.admin_service import AdminService

router = APIRouter(prefix="/users", tags=["User Management"])


# ==================== COLLECTION ROUTES (no path params) ====================


@router.get("", response_model=UserListResponse, summary="List all users")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    role: Optional[str] = Query(None, description="Filter by role name"),
    status_filter: Optional[UserStatus] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """List all users with optional filters and pagination."""
    return await AdminService.list_users(
        session,
        skip=skip,
        limit=limit,
        role=role,
        status_filter=status_filter,
        search=search,
    )


@router.post(
    "",
    response_model=UserWithRolesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    user_data: AdminUserCreate,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Admin creates a new user account."""
    return await AdminService.create_user(session, user_data, current_user)


# ==================== META ROUTES (before /{user_id} to avoid path conflicts) ==


@router.get("/deleted", response_model=UserListResponse, summary="List deleted users")
async def list_deleted_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """List all soft-deleted users with pagination."""
    return await AdminService.list_deleted_users(
        session,
        skip=skip,
        limit=limit,
        search=search,
    )


@router.get(
    "/meta/roles",
    response_model=list[RoleWithPermissions],
    summary="List all roles",
)
async def list_roles(
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """List all available roles with their permissions."""
    return await AdminService.list_roles(session)


@router.get(
    "/meta/permissions",
    response_model=list[PermissionResponse],
    summary="List all permissions",
)
async def list_permissions(
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """List all available permissions."""
    return await AdminService.list_permissions(session)


@router.put(
    "/meta/roles/{role_id}/permissions",
    response_model=RoleWithPermissions,
    summary="Set role permissions",
)
async def set_role_permissions(
    role_id: UUID,
    body: UpdateRolePermissionsRequest,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Replace all permissions for a role with the given set."""
    return await AdminService.set_role_permissions(
        session, role_id, body.permission_ids, current_user
    )


# ==================== USER DETAIL ROUTES (/{user_id}) ====================


@router.get("/{user_id}", response_model=UserWithRolesResponse, summary="Get user details")
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Get detailed user info by ID including roles."""
    return await AdminService.get_user(session, user_id)


@router.patch("/{user_id}", response_model=UserWithRolesResponse, summary="Update user")
async def update_user(
    user_id: UUID,
    updates: AdminUserUpdate,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Admin updates user profile."""
    return await AdminService.update_user(session, user_id, updates, current_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete user",
)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete a user."""
    await AdminService.delete_user(session, user_id, current_user)


@router.post(
    "/{user_id}/restore",
    response_model=UserWithRolesResponse,
    summary="Restore deleted user",
)
async def restore_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Restore a soft-deleted user."""
    return await AdminService.restore_user(session, user_id, current_user)


@router.delete(
    "/{user_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete user",
)
async def hard_delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Permanently delete a user from the database. This action cannot be undone."""
    await AdminService.hard_delete_user(session, user_id, current_user)


# ==================== ROLE ASSIGNMENT ====================


@router.post(
    "/{user_id}/roles",
    response_model=UserWithRolesResponse,
    summary="Assign roles to user",
)
async def assign_roles(
    user_id: UUID,
    body: AssignRoleRequest,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Assign one or more roles to a user."""
    return await AdminService.assign_roles(session, user_id, body.role_ids, current_user)


@router.delete(
    "/{user_id}/roles/{role_id}",
    response_model=UserWithRolesResponse,
    summary="Remove role from user",
)
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
):
    """Remove a specific role from a user."""
    return await AdminService.remove_role(session, user_id, role_id, current_user)
