"""``developer_admin`` is never granted through the API — ``CLAUDE.md`` §5.

It bypasses every permission check, so whoever holds it holds everything. The only way to
create one is ``app/iam/create_admin.py``. ``POST /users/{user_id}/roles`` used to assign any
role id it was given, which let a superuser mint new bypass accounts over HTTP.

These run without a database: the service is given in-memory CRUD fakes, and the refusal
happens before the session is ever touched.
"""

import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.iam.config import auth_config
from app.iam.exceptions import RoleNotGrantableError
from app.iam.permission.crud import RoleCRUD
from app.iam.user.crud import UserCRUD
from app.iam.user.models import User
from app.iam.user.services import AdminService


class _UserCRUD:
    def __init__(self, user: SimpleNamespace) -> None:
        self.user = user

    async def get_user_with_roles(self, session, user_id):
        return self.user


class _RoleCRUD:
    def __init__(self, *roles: SimpleNamespace) -> None:
        self.roles = {role.id: role for role in roles}
        self.added: list[uuid.UUID] = []

    async def get(self, session, role_id):
        return self.roles.get(role_id)

    async def add_user_role(self, session, user_id, role_id):
        self.added.append(role_id)


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), name=name)


async def test_developer_admin_is_refused_and_nothing_is_written() -> None:
    member, developer_admin = _role("member"), _role(auth_config.DEVELOPER_ADMIN_ROLE)
    user = SimpleNamespace(id=uuid.uuid4(), roles=[])
    roles = _RoleCRUD(member, developer_admin)
    # The fakes are test doubles; cast() says so to the type checker.
    service = AdminService(
        user_crud=cast(UserCRUD, _UserCRUD(user)), role_crud=cast(RoleCRUD, roles)
    )

    with pytest.raises(RoleNotGrantableError) as refused:
        await service.assign_roles(
            session=cast(AsyncSession, None),
            user_id=user.id,
            role_ids=[member.id, developer_admin.id],
            admin_user=cast(User, SimpleNamespace(email="admin@example.test")),
        )

    assert refused.value.status_code == 403
    # The allowed role listed first was not written either — the request is all or nothing.
    assert roles.added == []
