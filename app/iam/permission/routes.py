"""RBAC catalog admin routes — list roles/permissions, set role permissions.

Paths are preserved from the former ``user`` admin router (``/users/meta/*``) so
this is a pure refactor with no external API change.
"""

from uuid import UUID

from fastapi import APIRouter

from app.core.database import SessionDep
from app.user.dependencies import PermissionServiceDep, SuperUserDep
from app.user.permission_management.schemas import (
    PermissionResponse,
    RoleWithPermissions,
    UpdateRolePermissionsRequest,
)

rbac_router = APIRouter(prefix="/users/meta", tags=["RBAC Management"])


@rbac_router.get("/roles", summary="List all roles")
async def list_roles(
    session: SessionDep, _: SuperUserDep, service: PermissionServiceDep
) -> list[RoleWithPermissions]:
    return await service.list_roles(session)


@rbac_router.get("/permissions", summary="List all permissions")
async def list_permissions(
    session: SessionDep, _: SuperUserDep, service: PermissionServiceDep
) -> list[PermissionResponse]:
    return await service.list_permissions(session)


@rbac_router.put("/roles/{role_id}/permissions", summary="Set role permissions")
async def set_role_permissions(
    role_id: UUID,
    body: UpdateRolePermissionsRequest,
    session: SessionDep,
    current_user: SuperUserDep,
    service: PermissionServiceDep,
) -> RoleWithPermissions:
    return await service.set_role_permissions(
        session, role_id, body.permission_ids, current_user
    )
