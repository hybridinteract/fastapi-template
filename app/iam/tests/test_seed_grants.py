"""The seed never re-grants what an admin revoked — ``CLAUDE.md`` §5.

The seed runs in ``lifespan`` on every startup. It used to insert every missing catalogue grant
for every role, so a permission revoked on the access-control screen came back on the next
restart. Now a pair is seeded only when its role or its permission is new to the database.

These run without a database: ``_seed_role_permissions`` only calls ``add`` and ``flush``.
"""

import uuid
from types import SimpleNamespace
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.iam.permission.models import Permission, Role
from app.iam.seed import _seed_role_permissions


class _Session:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass


def _row(name: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), name=name)


async def _seed(mapping, roles, perms, pairs, known) -> set[tuple[str, str]]:
    session = _Session()
    await _seed_role_permissions(
        cast(AsyncSession, session),
        mapping,
        cast(dict[str, Role], roles),
        cast(dict[str, Permission], perms),
        pairs,
        known,
    )
    role_names = {r.id: name for name, r in roles.items()}
    perm_names = {p.id: name for name, p in perms.items()}
    return {(role_names[rp.role_id], perm_names[rp.permission_id]) for rp in session.added}


async def test_a_revoked_grant_stays_revoked() -> None:
    roles = {"admin": _row("admin")}
    perms = {"users:read": _row("users:read"), "users:delete": _row("users:delete")}
    # The admin revoked users:delete; only users:read is still granted.
    pairs = {(roles["admin"].id, perms["users:read"].id)}
    known = ({"admin"}, {"users:read", "users:delete"})

    added = await _seed({"admin": ["users:read", "users:delete"]}, roles, perms, pairs, known)

    assert added == set()


async def test_a_new_permission_reaches_an_existing_role() -> None:
    roles = {"admin": _row("admin")}
    perms = {"users:read": _row("users:read"), "reports:read": _row("reports:read")}
    pairs = {(roles["admin"].id, perms["users:read"].id)}
    known = ({"admin"}, {"users:read"})  # reports:read was created by this run

    added = await _seed({"admin": ["users:read", "reports:read"]}, roles, perms, pairs, known)

    assert added == {("admin", "reports:read")}


async def test_a_new_role_gets_its_full_catalogue_grant() -> None:
    roles = {"auditor": _row("auditor")}
    perms = {"users:read": _row("users:read"), "activity:read_all": _row("activity:read_all")}
    known: tuple[set[str], set[str]] = (set(), {"users:read", "activity:read_all"})

    added = await _seed(
        {"auditor": ["users:read", "activity:read_all"]}, roles, perms, set(), known
    )

    assert added == {("auditor", "users:read"), ("auditor", "activity:read_all")}
