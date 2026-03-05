"""
User Schemas Package.

Exports all schema classes for the user module.
"""

# Auth schemas (login, register, tokens)
from app.user.schemas.user_schemas import (
    UserBase,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserUpdateSelf,
    UserResponse,
    UserMinimal,
    TokenResponse,
    TokenRefresh,
    TokenPayload,
    ChangePasswordRequest,
)

# Admin schemas (user management, roles, permissions)
from app.user.schemas.admin_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    PermissionResponse,
    RoleResponse,
    RoleWithPermissions,
    AssignRoleRequest,
    UpdateRolePermissionsRequest,
    UserWithRolesResponse,
    UserListResponse,
)

__all__ = [
    # Auth
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserUpdateSelf",
    "UserResponse",
    "UserMinimal",
    "TokenResponse",
    "TokenRefresh",
    "TokenPayload",
    "ChangePasswordRequest",
    # Admin
    "AdminUserCreate",
    "AdminUserUpdate",
    "PermissionResponse",
    "RoleResponse",
    "RoleWithPermissions",
    "AssignRoleRequest",
    "UpdateRolePermissionsRequest",
    "UserWithRolesResponse",
    "UserListResponse",
]
