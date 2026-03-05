"""
Generic Scoped Access Framework.

Provides plugin-based scope infrastructure for data access control.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.orm import InstrumentedAttribute

from app.core.database import get_session
from app.user.models import User
from app.user.auth_management.utils import get_current_user_validated
from app.user.permission_management.utils import BasePermissionChecker


# ============== Scope Schema ==============

class AdminScope(BaseModel):
    """Generic admin scope - represents data access boundaries."""
    scope_type: str  # "global", "team", "department", etc.
    scope_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}

    @property
    def is_global(self) -> bool:
        return self.scope_type == "global"

    def is_scoped(self, scope_name: str) -> bool:
        return self.scope_type == scope_name


# ============== Scope Provider Interface ==============

class ScopeProvider(ABC):
    """Abstract interface for scope providers."""

    @property
    @abstractmethod
    def scope_name(self) -> str:
        """Unique name for this scope type."""
        pass

    @property
    @abstractmethod
    def permissions(self) -> List[str]:
        """Permissions that grant this scope."""
        pass

    @abstractmethod
    async def resolve_scope(
        self,
        session: AsyncSession,
        user: User
    ) -> AdminScope:
        """Resolve scope for a user."""
        pass

    @abstractmethod
    def apply_to_query(
        self,
        query: Select,
        scope: AdminScope,
        model: Any,
        user_id_column: str = "user_id",
        join_via: str = "direct",
        customer_columns: Optional[Dict[str, InstrumentedAttribute]] = None
    ) -> Select:
        """Apply scope filter to a SQLAlchemy query."""
        pass


# ============== Scope Registry ==============

class ScopeRegistry:
    """Registry for scope providers."""

    _providers: Dict[str, ScopeProvider] = {}

    @classmethod
    def register(cls, provider: ScopeProvider) -> None:
        cls._providers[provider.scope_name] = provider

    @classmethod
    def get(cls, scope_name: str) -> Optional[ScopeProvider]:
        return cls._providers.get(scope_name)

    @classmethod
    def get_by_permission(cls, permission: str) -> Optional[ScopeProvider]:
        for provider in cls._providers.values():
            if permission in provider.permissions:
                return provider
        return None

    @classmethod
    def all_scoped_permissions(cls) -> List[str]:
        perms = []
        for provider in cls._providers.values():
            perms.extend(provider.permissions)
        return perms

    @classmethod
    def clear(cls) -> None:
        cls._providers = {}


# ============== Scoped Permission Checker ==============

class ScopedPermissionChecker(BasePermissionChecker):
    """Permission checker that resolves admin scope."""

    def __init__(
        self,
        global_permissions: List[str],
        scoped_permissions: List[str]
    ):
        all_perms = global_permissions + scoped_permissions
        super().__init__(all_perms, require_all=False)
        self.global_permissions = global_permissions
        self.scoped_permissions = scoped_permissions

    async def __call__(
        self,
        current_user: User = Depends(get_current_user_validated),
        session: AsyncSession = Depends(get_session)
    ) -> tuple[User, AdminScope]:
        if await self.is_super_admin(session, current_user.id):
            return current_user, AdminScope(scope_type="global")

        user_perms = await self.get_user_permissions(session, current_user.id)

        if any(p in user_perms for p in self.global_permissions):
            return current_user, AdminScope(scope_type="global")

        for perm in self.scoped_permissions:
            if perm in user_perms:
                provider = ScopeRegistry.get_by_permission(perm)
                if provider:
                    scope = await provider.resolve_scope(session, current_user)
                    return current_user, scope

        self.handle_authorization_failure(current_user)
        raise Exception("Unreachable code")


def require_scoped_permission(
    global_permissions: List[str],
    scoped_permissions: List[str]
) -> ScopedPermissionChecker:
    return ScopedPermissionChecker(global_permissions, scoped_permissions)
