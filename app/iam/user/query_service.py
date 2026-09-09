"""Cached, read-only user lookups — the user module's query facade.

PURPOSE
    A read-through (cache-aside) layer over :class:`UserCRUD` for the handful of
    user lookups that are (a) read frequently and (b) safe to serve slightly
    stale. It returns Pydantic response DTOs — never ORM entities — so cached
    payloads are plain JSON and callers can't accidentally mutate a detached row.

WHEN TO USE
    • Read-only endpoints and *other modules* that need to resolve a user id to a
      profile / roles, list users by role, or bulk-resolve many ids (e.g. an
      assignment feature showing assignee names). Inject ``UserQueryServiceDep``
      and call the ``get_*`` methods.

WHEN **NOT** TO USE  (this is the important boundary)
    • Write paths and any read that immediately follows a write in the same
      request (e.g. ``AdminService.update_user`` re-reading the row it just
      committed). Those must use ``user_crud`` directly so they see authoritative
      data — routing them through the cache would risk serving the pre-write
      value (read-after-write self-poisoning).
    • The auth principal (``get_current_user``). Its cached fields
      (``is_active``, ``status``, roles) gate access, so staleness becomes a
      security issue; it deliberately stays on the database.

WHY A SEPARATE SERVICE (not caching inside ``UserService``)
    Invalidation is the hard part, and centralising it here keeps it correct:
      • one key schema in one place;
      • role *membership* changes need a wildcard bust of every role-list key,
        which can't be expressed as a per-method decorator key;
      • write paths stay cache-free, so the "authoritative read vs cached read"
        split is explicit rather than smeared across read methods.

CACHE INVALIDATION CONTRACT
    Any service that mutates a user (profile edit, create, soft/hard delete,
    restore, role assign/remove) MUST call :meth:`invalidate_user` **after**
    ``session.commit()`` — never before (a pre-commit bust lets a concurrent
    read re-cache a value that a rollback would erase). The cached DTOs carry
    role *names* but not permissions, so role-permission catalog edits do not
    affect this cache; a role *rename* (if ever added) should call
    :meth:`invalidate_all`.

EDGE CASES HANDLED
    • Cache disabled (``settings.CACHE_ENABLED=False``) → transparent passthrough.
    • Redis down → ``cache.get`` returns ``None`` and degrades to a DB read.
    • Negative results are never cached, so a just-created user is never masked.
    • Keys are version-prefixed (``:v1:``) so a DTO shape change can't deserialize
      stale payloads — bump the version instead of risking a bad ``model_validate``.
    • Bulk lookup serves per-id cache hits and issues a single DB query for the
      misses, preserving input order and de-duplicating ids.
    • TTLs carry jitter to avoid synchronized expiry (thundering herd) on hot
      role-list keys.
"""

import random
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.logging import get_logger
from app.core.settings import settings
from app.user.config import auth_config
from app.user.enums import UserStatus
from app.user.user.crud import UserCRUD, user_crud
from app.user.user.schemas import UserResponse, UserWithRolesResponse

logger = get_logger(__name__)

# Namespace + schema version. Bump the version segment whenever a cached DTO's
# shape changes so old payloads are ignored rather than mis-deserialized.
_NS = "user:query:v1"


class UserQueryService:
    """Read-through cache over :class:`UserCRUD` returning response DTOs."""

    def __init__(self, user_crud: UserCRUD):
        self._user_crud = user_crud

    # ── Cached reads ──────────────────────────────────────────────────────────

    async def get_user_by_id(
        self, session: AsyncSession, user_id: UUID
    ) -> Optional[UserResponse]:
        """Resolve a user id to its profile DTO; ``None`` if absent/deleted."""
        if not settings.CACHE_ENABLED:
            return await self._load_user(session, user_id)

        cached = await cache.get(self._id_key(user_id))
        if cached is not None:
            return UserResponse.model_validate(cached)

        dto = await self._load_user(session, user_id)
        if dto is not None:  # never cache misses
            await cache.set(self._id_key(user_id), dto.model_dump(mode="json"), ttl=self._ttl())
        return dto

    async def get_user_with_roles(
        self, session: AsyncSession, user_id: UUID
    ) -> Optional[UserWithRolesResponse]:
        """Like :meth:`get_user_by_id` but with roles eagerly included."""
        if not settings.CACHE_ENABLED:
            return await self._load_user_with_roles(session, user_id)

        cached = await cache.get(self._roles_key(user_id))
        if cached is not None:
            return UserWithRolesResponse.model_validate(cached)

        dto = await self._load_user_with_roles(session, user_id)
        if dto is not None:
            await cache.set(self._roles_key(user_id), dto.model_dump(mode="json"), ttl=self._ttl())
        return dto

    async def get_users_with_roles_by_ids(
        self, session: AsyncSession, user_ids: List[UUID]
    ) -> List[UserWithRolesResponse]:
        """Bulk-resolve ids: serve per-id hits, fetch misses in one query."""
        if not user_ids:
            return []
        unique_ids = list(dict.fromkeys(user_ids))  # dedupe, preserve order

        if not settings.CACHE_ENABLED:
            users = await self._user_crud.get_users_with_roles_by_ids(session, unique_ids)
            return [UserWithRolesResponse.model_validate(u) for u in users]

        found: dict[UUID, UserWithRolesResponse] = {}
        misses: list[UUID] = []
        for uid in unique_ids:
            cached = await cache.get(self._roles_key(uid))
            if cached is not None:
                found[uid] = UserWithRolesResponse.model_validate(cached)
            else:
                misses.append(uid)

        if misses:
            users = await self._user_crud.get_users_with_roles_by_ids(session, misses)
            for user in users:
                dto = UserWithRolesResponse.model_validate(user)
                found[user.id] = dto
                await cache.set(self._roles_key(user.id), dto.model_dump(mode="json"), ttl=self._ttl())

        return [found[uid] for uid in unique_ids if uid in found]

    async def get_active_users_by_role(
        self, session: AsyncSession, role: str
    ) -> List[UserResponse]:
        """List every active user holding ``role`` (cached per role name)."""
        if not settings.CACHE_ENABLED:
            return await self._load_active_users_by_role(session, role)

        cached = await cache.get(self._role_list_key(role))
        if cached is not None:
            return [UserResponse.model_validate(item) for item in cached]

        dtos = await self._load_active_users_by_role(session, role)
        if dtos:  # skip empty/None — don't pin an empty role list
            await cache.set(
                self._role_list_key(role),
                [dto.model_dump(mode="json") for dto in dtos],
                ttl=self._ttl(auth_config.USER_ROLE_LIST_CACHE_TTL_SECONDS),
            )
        return dtos

    # ── Invalidation (call AFTER commit from mutating services) ───────────────

    @staticmethod
    async def invalidate_user(user_id: UUID) -> None:
        """Drop a user's cached entries plus all role-list keys.

        Role lists are cleared wholesale because a membership change can add or
        remove the user from any role's list and we don't track which.
        """
        if not settings.CACHE_ENABLED:
            return
        await cache.delete(UserQueryService._id_key(user_id))
        await cache.delete(UserQueryService._roles_key(user_id))
        cleared = await cache.clear_pattern(f"{_NS}:role-list:*")
        logger.debug("User cache invalidated for %s (+%d role-list keys)", user_id, cleared)

    @staticmethod
    async def invalidate_all() -> None:
        """Nuke every key under this service's namespace (broad operations)."""
        if not settings.CACHE_ENABLED:
            return
        cleared = await cache.clear_pattern(f"{_NS}:*")
        if cleared:
            logger.debug("User query cache fully invalidated: %d keys", cleared)

    # ── DB loaders (authoritative, uncached) ──────────────────────────────────

    async def _load_user(self, session: AsyncSession, user_id: UUID) -> Optional[UserResponse]:
        user = await self._user_crud.get(session, user_id)
        if not user or user.is_deleted:
            return None
        return UserResponse.model_validate(user)

    async def _load_user_with_roles(
        self, session: AsyncSession, user_id: UUID
    ) -> Optional[UserWithRolesResponse]:
        user = await self._user_crud.get_user_with_roles(session, user_id)
        if not user:
            return None
        return UserWithRolesResponse.model_validate(user)

    async def _load_active_users_by_role(
        self, session: AsyncSession, role: str
    ) -> List[UserResponse]:
        users, _ = await self._user_crud.list_users_paginated(
            session, role=role, status=UserStatus.ACTIVE, skip=0, limit=10000
        )
        return [UserResponse.model_validate(u) for u in users]

    # ── Key + TTL helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _id_key(user_id: UUID) -> str:
        return f"{_NS}:id:{user_id}"

    @staticmethod
    def _roles_key(user_id: UUID) -> str:
        return f"{_NS}:roles:{user_id}"

    @staticmethod
    def _role_list_key(role: str) -> str:
        return f"{_NS}:role-list:{role}"

    @staticmethod
    def _ttl(base: Optional[int] = None) -> int:
        """TTL with up to +10% jitter to desynchronize expiries."""
        base = base if base is not None else auth_config.USER_CACHE_TTL_SECONDS
        return base + random.randint(0, max(1, base // 10))


# Module-level singleton (wired into DI in app.user.dependencies).
user_query_service = UserQueryService(user_crud=user_crud)
