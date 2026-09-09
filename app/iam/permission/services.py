"""RBAC catalog service — manage roles and permissions.

Owns the role/permission *catalog* (bucket 2). Assigning a role *to a user* is a
user-membership mutation and lives in ``user.services.AdminService`` (bucket 3).

Per conventions §4: this service owns commit/rollback; CRUD never commits.
Wired in ``app.iam.dependencies``.
"""

from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.iam.config import auth_config
from app.iam.permission.crud import PermissionCRUD, RoleCRUD
from app.iam.permission.schemas import (
    PermissionResponse,
    RoleWithPermissions,
)
from app.iam.user.models import User

logger = get_logger(__name__)


class PermissionService:
    """Admin management of the role/permission catalog."""

    def __init__(self, role_crud: RoleCRUD, permission_crud: PermissionCRUD):
        self.role_crud = role_crud
        self.permission_crud = permission_crud

    async def list_roles(self, session: AsyncSession) -> List[RoleWithPermissions]:
        roles = await self.role_crud.list_with_permissions(session)
        return [RoleWithPermissions.model_validate(r) for r in roles]

    async def list_permissions(self, session: AsyncSession) -> List[PermissionResponse]:
        perms = await self.permission_crud.list_all(session)
        return [PermissionResponse.model_validate(p) for p in perms]

    async def set_role_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_ids: List[UUID],
        admin_user: User,
    ) -> RoleWithPermissions:
        role = await self.role_crud.get_with_permissions(session, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        if role.name == auth_config.DEVELOPER_ADMIN_ROLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify {auth_config.DEVELOPER_ADMIN_ROLE} permissions",
            )

        await self.permission_crud.replace_role_permissions(
            session, role_id, permission_ids
        )
        await session.commit()

        role = await self.role_crud.get_with_permissions(session, role_id)
        logger.info(
            f"Admin {admin_user.email} updated permissions for role {role.name}"
        )
        return RoleWithPermissions.model_validate(role)
