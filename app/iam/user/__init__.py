"""User management submodule — CRUD, queries, schemas, and routes.

Routes are deliberately NOT eagerly imported here to keep this safe to import
from low-level helpers (e.g. ``auth.tokens``) without triggering circular loads.
Import ``user_router`` / ``admin_router`` directly from ``app.iam.user.routes``.
"""

from app.iam.user.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    AssignRoleRequest,
    RoleResponse,
    UserCreate,
    UserListResponse,
    UserMinimal,
    UserResponse,
    UserUpdate,
    UserUpdateSelf,
    UserWithRolesResponse,
)

__all__ = [
    "UserResponse",
    "UserMinimal",
    "UserCreate",
    "UserUpdate",
    "UserUpdateSelf",
    "UserWithRolesResponse",
    "UserListResponse",
    "AdminUserCreate",
    "AdminUserUpdate",
    "RoleResponse",
    "AssignRoleRequest",
]
