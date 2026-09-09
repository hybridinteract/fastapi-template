"""User & Auth Module V2 — pluggable auth + RBAC for FastAPI apps.

Drop-in portable: copy this folder into another FastAPI project. The only
external symbols the module depends on are:

    app.core.database.SessionDep        (async session DI)
    app.core.settings.settings          (JWT_SECRET_KEY, JWT_ALGORITHM)
    app.core.utils.utc_now
    app.core.logging.get_logger
    app.core.crud.CRUDBase              (base for CRUD classes)
    app.activity.activity (optional)    (activity-log adapter, no-op if absent)

To wire into a host app:
    from app.user import auth_router, user_router, admin_router, rbac_router, run_seed
    api.include_router(auth_router)
    api.include_router(user_router)
    api.include_router(admin_router)
    api.include_router(rbac_router)
    # in lifespan startup: await run_seed_operations(session)

Public API:
    from app.user import (
        User, Role, Permission,
        auth_router, user_router, admin_router,
        AuthConfig, auth_config,
        ExtraUserFieldsMixin,
        run_seed, run_seed_operations,
        CurrentUserDep, SuperUserDep,
        require_permission, require_any_permission, is_super_admin,
        Provider, PROVIDERS,
    )
"""

from app.user.auth import auth_router, build_auth_router
from app.user.auth.current_user import CurrentUserDep, SuperUserDep
from app.user.auth.providers import PROVIDERS, Provider
from app.user.config import AuthConfig, auth_config
from app.user.extensions import ExtraUserFieldsMixin
from app.user.permission_management.models import Permission, Role
from app.user.user.models import User
from app.user.permission_management import (
    has_permission,
    is_super_admin,
    require_all_permissions,
    require_any_permission,
    require_permission,
)
from app.user.permission_management.routes import rbac_router
from app.user.seed import run_seed, run_seed_operations
from app.user.user.routes import admin_router, user_router

__all__ = [
    # Routers
    "auth_router",
    "user_router",
    "admin_router",
    "rbac_router",
    "build_auth_router",
    # Models
    "User",
    "Role",
    "Permission",
    # Config
    "AuthConfig",
    "auth_config",
    # Extension points
    "ExtraUserFieldsMixin",
    "Provider",
    "PROVIDERS",
    # Seed
    "run_seed",
    "run_seed_operations",
    # Dependencies
    "CurrentUserDep",
    "SuperUserDep",
    # Permission guards
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
    "has_permission",
    "is_super_admin",
]
