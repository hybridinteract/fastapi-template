"""
Database seed script.

Seeds the minimum required roles and permissions for the platform to function.
Does NOT create any users — use `python -m app.user.create_admin` for that.

Usage:
    python -m app.user.seed

Base Roles:
    - super_admin: Full system access (bypasses all permission checks)
    - admin:       Administrative access to manage users and settings
    - member:      Standard authenticated user

Permission Format:
    Permissions follow the `resource:action` pattern stored in the Permission model.
    Scope variants use `resource:action:scope` (e.g. `users:read:all`).

Customization:
    Add project-specific roles to ROLES list.
    Add project-specific permissions to PERMISSIONS list.
    Update ROLE_PERMISSIONS to map roles to their permissions.
"""

import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, engine
from app.core.logging import get_logger
from app.user.models import (
    Role,
    Permission,
    RolePermission,
)

logger = get_logger(__name__)


# ──────────────────────────── Seed Data ────────────────────────────

ROLES = [
    {
        "name": "super_admin",
        "description": "Full system access. Bypasses all permission checks.",
        "is_system": True,
    },
    {
        "name": "admin",
        "description": "Administrative access: manage users, view reports, update settings.",
        "is_system": True,
    },
    {
        "name": "member",
        "description": "Standard authenticated user with basic access.",
        "is_system": True,
    },
]

# Permissions: (resource, action, description)
# These are the platform-level permissions applicable to every project.
# Add project-specific permissions below the "── Project-Specific ──" comment.
PERMISSIONS: list[tuple[str, str, str]] = [
    # ── Users ──
    ("users", "create",        "Create new user accounts"),
    ("users", "read",          "View user profiles"),
    ("users", "read_all",      "View all users in the system"),
    ("users", "update",        "Edit user accounts"),
    ("users", "delete",        "Delete user accounts"),
    ("users", "manage_roles",  "Assign/remove roles from users"),
    ("users", "reset_password","Reset user passwords"),
    ("users", "deactivate",    "Deactivate user accounts"),

    # ── Activity ──
    ("activity", "read",       "View activity logs"),
    ("activity", "read_all",   "View all activity logs"),
    ("activity", "read_own",   "View own activity"),

    # ── System ──
    ("system", "settings_read",    "View system settings"),
    ("system", "settings_update",  "Modify system settings"),
    ("system", "permissions_read", "View permissions matrix"),
    ("system", "permissions_update","Modify role permissions"),

    # ── Reports ──
    ("reports", "read",     "View reports and analytics"),
    ("reports", "read_own", "View own performance reports"),
    ("reports", "export",   "Export reports"),

    # ── Project-Specific ──
    # Add your project permissions here:
    # ("<resource>", "<action>", "<description>"),
]

# Role → list of "resource:action" permission names
ROLE_PERMISSIONS: dict[str, list[str]] = {
    # super_admin gets ALL permissions implicitly (bypasses checks),
    # but we still assign them for visibility in the permissions matrix.
    "super_admin": [f"{r}:{a}" for r, a, _ in PERMISSIONS],

    "admin": [
        # Users
        "users:create",
        "users:read",
        "users:read_all",
        "users:update",
        "users:delete",
        "users:manage_roles",
        "users:reset_password",
        "users:deactivate",
        # Activity
        "activity:read",
        "activity:read_all",
        # System
        "system:settings_read",
        "system:permissions_read",
        # Reports
        "reports:read",
        "reports:export",
    ],

    "member": [
        # Basic user access
        "users:read",
        # Own activity only
        "activity:read_own",
        # Own reports
        "reports:read_own",
    ],
}

# ──────────────────────────── Helpers ────────────────────────────


async def _seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    """Create permissions if they don't exist. Returns name→Permission map."""
    existing = (await session.execute(select(Permission))).scalars().all()
    existing_map = {p.name: p for p in existing}

    created = 0
    for resource, action, description in PERMISSIONS:
        name = f"{resource}:{action}"
        if name not in existing_map:
            perm = Permission(
                id=uuid4(),
                name=name,
                resource=resource,
                action=action,
                description=description,
            )
            session.add(perm)
            existing_map[name] = perm
            created += 1

    if created:
        await session.flush()
        logger.info(f"Created {created} permissions")
    else:
        logger.info("All permissions already exist")

    return existing_map


async def _seed_roles(session: AsyncSession) -> dict[str, Role]:
    """Create roles if they don't exist. Returns name→Role map."""
    existing = (await session.execute(select(Role))).scalars().all()
    existing_map = {r.name: r for r in existing}

    created = 0
    for role_data in ROLES:
        if role_data["name"] not in existing_map:
            role = Role(id=uuid4(), **role_data)
            session.add(role)
            existing_map[role_data["name"]] = role
            created += 1

    if created:
        await session.flush()
        logger.info(f"Created {created} roles")
    else:
        logger.info("All roles already exist")

    return existing_map


async def _seed_role_permissions(
    session: AsyncSession,
    roles: dict[str, Role],
    permissions: dict[str, Permission],
) -> None:
    """Link roles to their permissions."""
    # Load existing role-permission links
    existing_rp = (await session.execute(select(RolePermission))).scalars().all()
    existing_pairs = {(rp.role_id, rp.permission_id) for rp in existing_rp}

    created = 0
    for role_name, perm_names in ROLE_PERMISSIONS.items():
        role = roles.get(role_name)
        if not role:
            continue
        for perm_name in perm_names:
            perm = permissions.get(perm_name)
            if not perm:
                logger.warning(f"Permission '{perm_name}' not found, skipping")
                continue
            if (role.id, perm.id) not in existing_pairs:
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                session.add(rp)
                existing_pairs.add((role.id, perm.id))
                created += 1

    if created:
        await session.flush()
        logger.info(f"Created {created} role-permission links")
    else:
        logger.info("All role-permission links already exist")


# ──────────────────────────── Main ────────────────────────────


async def run_seed(dispose_engine: bool = True) -> None:
    """Run all seed operations inside a single transaction.

    Args:
        dispose_engine: If True, dispose the engine after seeding.
                       Set to False when running at application startup.
    """
    logger.info("Starting database seed...")

    try:
        async with async_session_factory() as session:
            async with session.begin():
                permissions = await _seed_permissions(session)
                roles = await _seed_roles(session)
                await _seed_role_permissions(session, roles, permissions)

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
