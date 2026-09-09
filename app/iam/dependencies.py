"""Module DI wiring layer (REQUIRED per conventions §5).

The single place where CRUD singletons are wired into per-request services and
exposed to routes as ``Annotated`` ``Dep`` aliases. No business logic lives here.
"""

from functools import cache
from typing import Annotated

from fastapi import Depends

from app.user.auth.current_user import (
    CurrentUserDep,
    SuperUserDep,
    get_current_active_superuser,
    get_current_user,
)
from app.user.auth.services import AccountProvisioningService, TokenService
from app.user.auth.crud import oauth_account_crud, refresh_token_crud
from app.user.permission_management.crud import permission_crud, role_crud
from app.user.permission_management.services import PermissionService
from app.user.user.crud import user_crud
from app.user.user.query_service import UserQueryService, user_query_service
from app.user.user.services import AdminService, UserService


# ── Service factories ─────────────────────────────────────────────────────────
# Services are stateless (CRUD refs only); cache app-wide to skip per-request
# construction. FastAPI's Depends already caches within a single request.

@cache
def get_token_service() -> TokenService:
    return TokenService(user_crud=user_crud, refresh_token_crud=refresh_token_crud)


@cache
def get_account_provisioning_service() -> AccountProvisioningService:
    return AccountProvisioningService(
        user_crud=user_crud, oauth_account_crud=oauth_account_crud
    )


@cache
def get_user_service() -> UserService:
    return UserService(
        user_crud=user_crud,
        oauth_account_crud=oauth_account_crud,
        user_query_service=user_query_service,
    )


@cache
def get_admin_service() -> AdminService:
    return AdminService(user_crud=user_crud, role_crud=role_crud)


@cache
def get_permission_service() -> PermissionService:
    return PermissionService(role_crud=role_crud, permission_crud=permission_crud)


def get_user_query_service() -> UserQueryService:
    # Already a configured module singleton; expose it via DI for routes/cross-module.
    return user_query_service


# ── Annotated Dep aliases for route signatures ────────────────────────────────

TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
AccountProvisioningServiceDep = Annotated[
    AccountProvisioningService, Depends(get_account_provisioning_service)
]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
PermissionServiceDep = Annotated[PermissionService, Depends(get_permission_service)]
UserQueryServiceDep = Annotated[UserQueryService, Depends(get_user_query_service)]


__all__ = [
    # Service Deps
    "TokenServiceDep",
    "AccountProvisioningServiceDep",
    "UserServiceDep",
    "AdminServiceDep",
    "PermissionServiceDep",
    "UserQueryServiceDep",
    # Current-user Deps (re-exported for convenience)
    "CurrentUserDep",
    "SuperUserDep",
    "get_current_user",
    "get_current_active_superuser",
]
