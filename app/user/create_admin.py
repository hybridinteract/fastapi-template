"""
Interactive super admin creation script.

Collects credentials from the terminal and creates a super admin user
with the super_admin role assigned.

Usage:
    python -m app.user.create_admin            # Interactive — creates admin only
    python -m app.user.create_admin --force     # Auto-creates seeded dev/test users

Requires:
    - Database migrations applied
    - Roles seeded (run `python -m app.user.seed` first)

Customization (--force mode):
    Edit the FORCE_USERS list below to define the dev/test accounts your
    project needs. These users are only created when the role exists in DB,
    so they are safe to run repeatedly (idempotent).
"""

import asyncio
import getpass
import re
import sys
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, engine
from app.core.logging import get_logger
from app.user.auth_management.utils import get_password_hash
from app.user.models import User, UserStatus, Role, UserRole

logger = get_logger(__name__)

SUPER_ADMIN_ROLE = "super_admin"
MIN_PASSWORD_LENGTH = 8

# Default password used for --force seeded users.
# Change this in your project; never use a trivial password in staging/production.
_FORCE_PASSWORD = "Dev@12345"

# ──────────────────────────────────────────────────────────────
# FORCE_USERS — edit this list for your project's dev/test accounts.
#
# Each entry must have:
#   full_name (str), email (str), password (str),
#   phone (str|None), role (str), is_superuser (bool)
# ──────────────────────────────────────────────────────────────
FORCE_USERS = [
    {
        "full_name": "App Super Admin",
        "email": "admin@example.com",
        "password": _FORCE_PASSWORD,
        "phone": None,
        "role": "super_admin",
        "is_superuser": True,
    },
    {
        "full_name": "App Admin User",
        "email": "appAdmin@example.com",
        "password": _FORCE_PASSWORD,
        "phone": None,
        "role": "admin",
        "is_superuser": False,
    },
    {
        "full_name": "App Member User",
        "email": "member@example.com",
        "password": _FORCE_PASSWORD,
        "phone": None,
        "role": "member",
        "is_superuser": False,
    },
    # Add more project-specific role users below:
    # {
    #     "full_name": "...",
    #     "email": "...@example.com",
    #     "password": _FORCE_PASSWORD,
    #     "phone": None,
    #     "role": "<your_role>",
    #     "is_superuser": False,
    # },
]


# ──────────────────────────── Validation ────────────────────────────


def validate_email(email: str) -> str | None:
    """Return error message if email is invalid, else None."""
    if not email or not email.strip():
        return "Email cannot be empty."
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email.strip()):
        return "Invalid email format."
    return None


def validate_password(password: str) -> str | None:
    """Return error message if password is weak, else None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    if not re.search(r"[^a-zA-Z0-9]", password):
        return "Password must contain at least one special character."
    return None


def validate_full_name(name: str) -> str | None:
    """Return error message if name is invalid, else None."""
    if not name or not name.strip():
        return "Full name cannot be empty."
    if len(name.strip()) < 2:
        return "Full name must be at least 2 characters."
    return None


# ──────────────────────────── Input Collection ────────────────────────────


def collect_input() -> dict:
    """Interactively collect super admin details from the terminal."""
    print()
    print("=" * 50)
    print("  Create Super Admin User")
    print("=" * 50)
    print()

    # Full name
    while True:
        full_name = input("Full name: ").strip()
        error = validate_full_name(full_name)
        if error:
            print(f"  Error: {error}")
            continue
        break

    # Email
    while True:
        email = input("Email: ").strip().lower()
        error = validate_email(email)
        if error:
            print(f"  Error: {error}")
            continue
        break

    # Password (hidden input)
    while True:
        password = getpass.getpass("Password: ")
        error = validate_password(password)
        if error:
            print(f"  Error: {error}")
            continue

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("  Error: Passwords do not match.")
            continue
        break

    # Phone (optional)
    phone = input("Phone (optional, press Enter to skip): ").strip() or None

    return {
        "full_name": full_name,
        "email": email,
        "password": password,
        "phone": phone,
    }


# ──────────────────────────── DB Operations ────────────────────────────


async def _get_role(session: AsyncSession, role_name: str) -> Role:
    """Fetch a role by name or exit with error."""
    result = await session.execute(
        select(Role).where(Role.name == role_name)
    )
    role = result.scalar_one_or_none()
    if not role:
        print(f"\n  Error: '{role_name}' role not found in database.")
        print("  Run `python -m app.user.seed` first to seed roles.")
        sys.exit(1)
    return role


async def _email_exists(session: AsyncSession, email: str) -> bool:
    """Check if a user with this email already exists."""
    result = await session.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none() is not None


async def create_super_admin(data: dict) -> None:
    """Create the super admin user in the database."""
    async with async_session_factory() as session:
        async with session.begin():
            # Check if email already exists
            if await _email_exists(session, data["email"]):
                print(f"\n  Error: A user with email '{data['email']}' already exists.")
                print("  Use a different email or update the existing user.")
                sys.exit(1)

            # Check if phone already exists (when provided)
            if data["phone"]:
                existing_phone = await session.execute(
                    select(User).where(User.phone == data["phone"])
                )
                if existing_phone.scalar_one_or_none():
                    print(f"\n  Error: A user with phone '{data['phone']}' already exists.")
                    sys.exit(1)

            # Verify super_admin role exists
            sa_role = await _get_role(session, SUPER_ADMIN_ROLE)

            # Create user
            user = User(
                id=uuid4(),
                email=data["email"],
                hashed_password=get_password_hash(data["password"]),
                full_name=data["full_name"],
                phone=data["phone"],
                email_verified=True,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_superuser=True,
            )
            session.add(user)
            await session.flush()

            # Assign super_admin role
            session.add(UserRole(user_id=user.id, role_id=sa_role.id))
            await session.flush()

    print()
    print("-" * 50)
    print("  Super admin created successfully!")
    print(f"  Email: {data['email']}")
    print(f"  Name:  {data['full_name']}")
    print("-" * 50)
    print()


async def create_force_users() -> None:
    """Auto-create all FORCE_USERS seeded accounts."""
    print()
    print("=" * 50)
    print("  Force Mode — Creating All Role Users")
    print("=" * 50)
    print()

    async with async_session_factory() as session:
        async with session.begin():
            # Pre-load all needed roles
            role_result = await session.execute(select(Role))
            role_map = {r.name: r for r in role_result.scalars().all()}

            created = 0
            skipped = 0

            for user_data in FORCE_USERS:
                role_name = user_data["role"]

                # Verify role exists
                if role_name not in role_map:
                    print(f"  SKIP  '{role_name}' role not found — run seed first")
                    skipped += 1
                    continue

                # Skip if email already exists
                if await _email_exists(session, user_data["email"]):
                    print(f"  SKIP  {user_data['email']} (already exists)")
                    skipped += 1
                    continue

                # Create user
                user = User(
                    id=uuid4(),
                    email=user_data["email"],
                    hashed_password=get_password_hash(user_data["password"]),
                    full_name=user_data["full_name"],
                    phone=user_data["phone"],
                    email_verified=True,
                    status=UserStatus.ACTIVE,
                    is_active=True,
                    is_superuser=user_data["is_superuser"],
                )
                session.add(user)
                await session.flush()

                # Assign role
                session.add(UserRole(user_id=user.id, role_id=role_map[role_name].id))
                await session.flush()

                print(f"  OK    {user_data['email']} ({role_name})")
                created += 1

    print()
    print("-" * 50)
    print(f"  Done! Created: {created}, Skipped: {skipped}")
    if created > 0:
        print(f"  Password for all new users: {_FORCE_PASSWORD}")
    print("-" * 50)
    print()


# ──────────────────────────── Entry Point ────────────────────────────


async def _run_interactive(data: dict) -> None:
    try:
        await create_super_admin(data)
    finally:
        await engine.dispose()


async def _run_force() -> None:
    try:
        await create_force_users()
    finally:
        await engine.dispose()


def main() -> None:
    """Entry point for `python -m app.user.create_admin`."""
    force = "--force" in sys.argv

    if force:
        try:
            asyncio.run(_run_force())
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"Force user creation failed: {e}")
            print(f"\n  Error: {e}")
            sys.exit(1)
    else:
        try:
            data = collect_input()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Cancelled.")
            sys.exit(0)

        try:
            asyncio.run(_run_interactive(data))
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"Failed to create super admin: {e}")
            print(f"\n  Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
