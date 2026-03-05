"""
Permission Management Module

Provides RBAC functionality and Scoped Access Control.
"""

from .utils import (
    require_permission,
    require_any_permission,
    require_all_permissions,
    has_permission,
    is_super_admin,
    PermissionChecker,
    SUPER_ADMIN_ROLE,
    BasePermissionChecker,
)
from .scoped_access import (
    AdminScope,
    ScopeProvider,
    ScopeRegistry,
    ScopedPermissionChecker,
    require_scoped_permission
)

__all__ = [
    # Utilities
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
    "has_permission",
    "is_super_admin",
    "PermissionChecker",
    "SUPER_ADMIN_ROLE",
    "BasePermissionChecker",

    # Scoped Access Framework
    "AdminScope",
    "ScopeProvider",
    "ScopeRegistry",
    "ScopedPermissionChecker",
    "require_scoped_permission",
]
