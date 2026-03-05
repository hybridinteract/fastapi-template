"""
User Query Service — Shared, read-only user lookups with Redis caching.

This service is strictly for retrieving and verifying User data.

Other modules that need to verify users (e.g. for assignment) should
inject this instead of UserCRUD when they need to:
  - Resolve a user ID to a display name
  - Validate a user's existence / role / status
  - List users by role

All methods are pure reads — no creates, updates, or deletes.
Caching is handled transparently; callers don't need to know about Redis.

Cache Invalidation:
    Call ``invalidate_user_cache()`` from AdminService / UserService
    whenever a user is created, updated, deleted, or has roles changed.
"""

from app.user.crud import user_crud as _user_crud_instance
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.logging import get_logger
from app.core.settings import settings
from app.user.crud import UserCRUD
from app.user.models import User, UserStatus

logger = get_logger(__name__)

# ==================== CACHE CONFIGURATION ====================

_USER_CACHE_PREFIX = "user:query"
_USER_CACHE_TTL = 900          # 15 minutes for individual lookups
_ROLE_LIST_CACHE_TTL = 900     # 15 minutes for role-based lists


class UserQueryService:
    """
    Read-only user query layer with Redis caching.

    Designed to be injected into services in other modules that need
    user data without owning the user module.  Returns lightweight
    dictionaries from cache or full ORM ``User`` objects on cache miss
    (which are then cached for subsequent calls).
    """

    def __init__(self, user_crud: UserCRUD):
        self._user_crud = user_crud

    # ==================== PUBLIC READ METHODS ====================

    async def get_user_by_id(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> Optional[User]:
        """
        Get a user by ID with caching.

        Used to resolve a user UUID to a full User object with caching.

        Returns:
            User ORM object, or None if not found.
        """
        cache_key = f"{_USER_CACHE_PREFIX}:id:{user_id}"

        # --- Try cache first ---
        if settings.CACHE_ENABLED:
            cached_data = await cache.get(cache_key)
            if cached_data is not None:
                return self._dict_to_user(cached_data)

        # --- Cache miss → DB ---
        user = await self._user_crud.get(session, user_id)
        if not user:
            return None

        # Store in cache
        if settings.CACHE_ENABLED:
            await cache.set(cache_key, self._user_to_dict(user), ttl=_USER_CACHE_TTL)

        return user

    async def get_user_with_roles(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> Optional[User]:
        """
        Get a user by ID with roles eagerly loaded.

        Useful when callers need to inspect the user's assigned roles
        (e.g. for role-based validation in other modules).

        Returns:
            User ORM object with ``roles`` populated, or None.
        """
        cache_key = f"{_USER_CACHE_PREFIX}:id_roles:{user_id}"

        # --- Try cache first ---
        if settings.CACHE_ENABLED:
            cached_data = await cache.get(cache_key)
            if cached_data is not None:
                return self._dict_to_user_with_roles(cached_data)

        # --- Cache miss → DB ---
        user = await self._user_crud.get_user_with_roles(session, user_id)
        if not user:
            return None

        # Store in cache
        if settings.CACHE_ENABLED:
            await cache.set(
                cache_key,
                self._user_to_dict_with_roles(user),
                ttl=_USER_CACHE_TTL,
            )

        return user

    async def get_users_with_roles_by_ids(
        self,
        session: AsyncSession,
        user_ids: List[UUID],
    ) -> List[User]:
        """
        Get multiple users by IDs with roles eagerly loaded.
        """
        if not user_ids:
            return []

        unique_ids = list(set(user_ids))

        # Fetch directly from DB for bulk operations to ensure consistency
        users = await self._user_crud.get_users_with_roles_by_ids(session, unique_ids)

        # Populate cache
        if settings.CACHE_ENABLED and users:
            for user in users:
                cache_key = f"{_USER_CACHE_PREFIX}:id_roles:{user.id}"
                await cache.set(
                    cache_key,
                    self._user_to_dict_with_roles(user),
                    ttl=_USER_CACHE_TTL,
                )

        return users

    async def get_active_users_by_role(
        self,
        session: AsyncSession,
        role: str,
    ) -> List[User]:
        """
        Get all active users for a given role, with caching.

        Returns:
            List of active User ORM objects that hold the requested role.
        """
        cache_key = f"{_USER_CACHE_PREFIX}:role:{role}:active"

        # --- Try cache first ---
        if settings.CACHE_ENABLED:
            cached_data = await cache.get(cache_key)
            if cached_data is not None:
                return [self._dict_to_user(u) for u in cached_data]

        # --- Cache miss → DB ---
        users, _ = await self._user_crud.list_users_paginated(
            session,
            role=role,
            status=UserStatus.ACTIVE,
            skip=0,
            limit=10000,
        )

        # Store in cache
        if settings.CACHE_ENABLED and users:
            await cache.set(
                cache_key,
                [self._user_to_dict(u) for u in users],
                ttl=_ROLE_LIST_CACHE_TTL,
            )

        return users

    # ==================== CACHE INVALIDATION ====================

    @staticmethod
    async def invalidate_user_cache(user_id: Optional[UUID] = None) -> None:
        """
        Invalidate user query caches.

        Should be called by AdminService / UserService after any user
        mutation (create, update, delete, role change, restore).

        Args:
            user_id: If provided, invalidate only that user's keys
                     plus the role lists.  If None, invalidate everything.
        """
        if not settings.CACHE_ENABLED:
            return

        if user_id:
            # Targeted invalidation: specific user + role lists
            await cache.delete(f"{_USER_CACHE_PREFIX}:id:{user_id}")
            await cache.delete(f"{_USER_CACHE_PREFIX}:id_roles:{user_id}")
            # Role lists must be fully cleared because we don't know
            # which roles the user belongs to (or used to belong to).
            deleted = await cache.clear_pattern(f"{_USER_CACHE_PREFIX}:role:*")
            logger.debug(
                f"User cache invalidated for user {user_id} "
                f"(+ {deleted} role-list keys)"
            )
        else:
            # Nuclear option: clear everything under our prefix
            deleted = await cache.clear_pattern(f"{_USER_CACHE_PREFIX}:*")
            if deleted:
                logger.debug(f"User cache fully invalidated: {deleted} keys")

    # ==================== SERIALISATION HELPERS ====================

    @staticmethod
    def _user_to_dict(user: User) -> dict:
        """Serialize a User ORM object to a cache-safe dictionary."""
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status.value if isinstance(user.status, UserStatus) else user.status,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "department": user.department,
            "email_verified": user.email_verified,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "is_deleted": user.is_deleted,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

    @staticmethod
    def _user_to_dict_with_roles(user: User) -> dict:
        """Serialize a User with roles to a cache-safe dictionary."""
        data = UserQueryService._user_to_dict(user)
        data["roles"] = [
            {"id": str(r.id), "name": r.name}
            for r in (user.roles or [])
        ]
        return data

    @staticmethod
    def _dict_to_user(data: dict) -> User:
        """
        Reconstruct a lightweight User object from cached data.

        This creates a *detached* User (not bound to any session).
        It's suitable for read-only operations like extracting
        ``full_name`` or ``email`` — not for further DB mutations.
        """
        from datetime import datetime

        user = User()
        user.id = UUID(data["id"]) if isinstance(
            data["id"], str) else data["id"]
        user.email = data["email"]
        user.full_name = data.get("full_name")
        user.status = UserStatus(data["status"]) if data.get(
            "status") else UserStatus.ACTIVE
        user.phone = data.get("phone")
        user.avatar_url = data.get("avatar_url")
        user.department = data.get("department")
        user.email_verified = data.get("email_verified", False)
        user.is_active = data.get("is_active", True)
        user.is_superuser = data.get("is_superuser", False)
        user.is_deleted = data.get("is_deleted", False)

        # DateTime fields
        if data.get("last_login_at"):
            user.last_login_at = datetime.fromisoformat(data["last_login_at"])
        else:
            user.last_login_at = None

        if data.get("created_at"):
            user.created_at = datetime.fromisoformat(data["created_at"])
        else:
            user.created_at = None

        if data.get("updated_at"):
            user.updated_at = datetime.fromisoformat(data["updated_at"])
        else:
            user.updated_at = None

        return user

    @staticmethod
    def _dict_to_user_with_roles(data: dict) -> User:
        """
        Reconstruct a User with roles from cached data.

        Roles are stored as lightweight objects with ``id`` and ``name``
        so that callers can iterate ``user.roles`` for role checks.
        """
        from app.user.models import Role

        user = UserQueryService._dict_to_user(data)

        roles = []
        for r in data.get("roles", []):
            role = Role()
            role.id = UUID(r["id"]) if isinstance(r["id"], str) else r["id"]
            role.name = r["name"]
            roles.append(role)

        user.roles = roles
        return user


# Module-level singleton (uses the global user_crud instance)

user_query_service = UserQueryService(user_crud=_user_crud_instance)
