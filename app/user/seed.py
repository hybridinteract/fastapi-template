"""Database seed for User V2 — one entry point: ``run_seed``."""

import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, engine
from app.core.logging import get_logger
from app.user import extensions
from app.user.permission_management.models import Permission, Role, RolePermission
from app.user.permissions import (
    PLATFORM_PERMISSIONS,
    PLATFORM_ROLES,
    PLATFORM_ROLE_PERMISSIONS,
)

logger = get_logger(__name__)


async def _seed_permissions(
    session: AsyncSession,
    items: list[tuple[str, str, str]],
    existing: dict[str, Permission],
) -> int:
    created = 0
    for resource, action, description in items:
        name = f"{resource}:{action}"
        if name not in existing:
            perm = Permission(
                id=uuid4(),
                name=name,
                resource=resource,
                action=action,
                description=description,
            )
            session.add(perm)
            existing[name] = perm
            created += 1
    if created:
        await session.flush()
    return created


async def _seed_roles(
    session: AsyncSession,
    items: list[dict],
    existing: dict[str, Role],
) -> int:
    created = 0
    for role_data in items:
        if role_data["name"] not in existing:
            role = Role(id=uuid4(), **role_data)
            session.add(role)
            existing[role_data["name"]] = role
            created += 1
    if created:
        await session.flush()
    return created


async def _seed_role_permissions(
    session: AsyncSession,
    mapping: dict[str, list[str]],
    roles: dict[str, Role],
    permissions: dict[str, Permission],
    existing_pairs: set[tuple],
) -> int:
    created = 0
    for role_name, perm_names in mapping.items():
        role = roles.get(role_name)
        if not role:
            continue
        for perm_name in perm_names:
            perm = permissions.get(perm_name)
            if not perm:
                continue
            if (role.id, perm.id) not in existing_pairs:
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))
                existing_pairs.add((role.id, perm.id))
                created += 1
    if created:
        await session.flush()
    return created


async def run_seed_operations(session: AsyncSession) -> None:
    """Seed core + provider + extension permissions/roles inside an existing transaction."""
    # Load current state once
    existing_perms = {p.name: p for p in (await session.execute(select(Permission))).scalars().all()}
    existing_roles = {r.name: r for r in (await session.execute(select(Role))).scalars().all()}
    existing_pairs = {
        (rp.role_id, rp.permission_id)
        for rp in (await session.execute(select(RolePermission))).scalars().all()
    }

    # 1. Core permissions, roles, role-permission links
    p = await _seed_permissions(session, PLATFORM_PERMISSIONS, existing_perms)
    r = await _seed_roles(session, PLATFORM_ROLES, existing_roles)
    rp = await _seed_role_permissions(
        session, PLATFORM_ROLE_PERMISSIONS, existing_roles, existing_perms, existing_pairs
    )
    if p: logger.info(f"Created {p} core permissions")
    if r: logger.info(f"Created {r} core roles")
    if rp: logger.info(f"Created {rp} core role-permission links")

    # 2. Provider permissions (importing here ensures providers are registered)
    from app.user.auth.providers import PROVIDERS
    provider_perms = []
    provider_role_mappings: dict[str, list[str]] = {}
    for prov in PROVIDERS:
        provider_perms.extend(prov.permissions)
        for role_name, perm_names in prov.role_permissions.items():
            provider_role_mappings.setdefault(role_name, []).extend(perm_names)

    pp = await _seed_permissions(session, provider_perms, existing_perms)
    prp = await _seed_role_permissions(
        session, provider_role_mappings, existing_roles, existing_perms, existing_pairs
    )
    if pp: logger.info(f"Created {pp} provider permissions")
    if prp: logger.info(f"Created {prp} provider role-permission links")

    # 3. Extension permissions, roles, role-permission links
    ep = await _seed_permissions(session, extensions.extra_permissions(), existing_perms)
    er = await _seed_roles(session, extensions.extra_roles(), existing_roles)
    erp = await _seed_role_permissions(
        session, extensions.extra_role_permissions(), existing_roles, existing_perms, existing_pairs
    )
    if ep: logger.info(f"Created {ep} extension permissions")
    if er: logger.info(f"Created {er} extension roles")
    if erp: logger.info(f"Created {erp} extension role-permission links")


async def run_seed(dispose_engine: bool = True) -> None:
    """Open a session and run all seed operations in a single transaction."""
    logger.info("Starting database seed...")
    try:
        async with async_session_factory() as session:
            async with session.begin():
                await run_seed_operations(session)
        logger.info("Database seed completed successfully")
    finally:
        if dispose_engine:
            await engine.dispose()


def main() -> None:
    """Entry point for `python -m app.user.seed`."""
    try:
        asyncio.run(run_seed())
    except KeyboardInterrupt:
        logger.info("Seed interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Seed failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
