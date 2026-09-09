"""RBAC admin Pydantic schemas — role/permission catalog shapes.

``RoleResponse`` stays in ``user.schemas`` because ``UserWithRolesResponse``
embeds it; we extend it here for the permission-bearing variant.
"""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.user.user.schemas import RoleResponse


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class RoleWithPermissions(RoleResponse):
    permissions: List[PermissionResponse] = []


class UpdateRolePermissionsRequest(BaseModel):
    permission_ids: List[UUID]
