"""
Permission Management Utilities

Comprehensive RBAC utilities and PermissionChecker.
"""

from typing import List, Set, Optional, Union
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists as sql_exists
from app.core.database import get_session
from app.core.logging import get_logger
from app.user.auth_management.utils import get_current_user_validated
from app.user.models import User as UserModel, Permission, Role, UserRole, RolePermission

logger = get_logger(__name__)

SUPER_ADMIN_ROLE = "super_admin"


class BasePermissionChecker:
    """Base permission checker for super admin + basic RBAC authorization."""

    def __init__(
        self,
        required_permissions: Optional[Union[str, List[str]]] = None,
        require_all: bool = True
    ):
        if required_permissions:
            if isinstance(required_permissions, str):
                required_permissions = [required_permissions]
            self.required_permissions = required_permissions
        else:
            self.required_permissions = []
        self.require_all = require_all

    async def __call__(
        self,
        current_user: UserModel = Depends(get_current_user_validated),
        session: AsyncSession = Depends(get_session)
    ) -> UserModel:
        if await self.is_super_admin(session, current_user.id):
            return current_user

        if self.required_permissions:
            user_permissions = await self.get_user_permissions(session, current_user.id)
            has_access = False
            if self.require_all:
                has_access = all(
                    perm in user_permissions for perm in self.required_permissions)
            else:
                has_access = any(
                    perm in user_permissions for perm in self.required_permissions)
            if has_access:
                return current_user

        self.handle_authorization_failure(current_user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    def handle_authorization_failure(self, current_user: UserModel) -> None:
        logger.warning(
            f"Permission denied for user {current_user.id}. Required: {self.required_permissions}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission(s): {', '.join(self.required_permissions)}"
        )

    @staticmethod
    async def is_super_admin(session: AsyncSession, user_id: Union[str, UUID]) -> bool:
        query = select(
            sql_exists()
            .where(UserRole.user_id == user_id)
            .where(Role.name == SUPER_ADMIN_ROLE)
            .where(UserRole.role_id == Role.id)
            .correlate(UserRole, Role)
        )
        result = await session.execute(query)
        return result.scalar()

    @staticmethod
    async def get_user_permissions(session: AsyncSession, user_id: Union[str, UUID]) -> Set[str]:
        query = (
            select(Permission.name.distinct())
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        )
        result = await session.execute(query)
        return set(result.scalars().all())


class PermissionChecker(BasePermissionChecker):
    """Standard permission checker for pure RBAC authorization."""
    pass


def require_permission(permission: str) -> PermissionChecker:
    return PermissionChecker(permission)


def require_any_permission(*permissions: str) -> PermissionChecker:
    return PermissionChecker(list(permissions), require_all=False)


def require_all_permissions(*permissions: str) -> PermissionChecker:
    return PermissionChecker(list(permissions), require_all=True)


async def has_permission(user: UserModel, permission: str, session: AsyncSession) -> bool:
    if await BasePermissionChecker.is_super_admin(session, user.id):
        return True
    user_permissions = await BasePermissionChecker.get_user_permissions(session, user.id)
    return permission in user_permissions


async def is_super_admin(user: UserModel, session: AsyncSession) -> bool:
    return await BasePermissionChecker.is_super_admin(session, user.id)
