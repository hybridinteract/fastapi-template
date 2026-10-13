"""Admin user changes keep their guards and leave an audit record.

- A restored user keeps the status they had: a suspension survives delete-then-restore.
- An admin cannot give a user a phone number another user already has.
- Role assignment and removal, role-permission edits and hard deletes are audited.

These run without a database: the services get in-memory CRUD fakes, ``log_activity`` is
recorded instead of dispatched, and the response models are passed through.
"""

import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.iam.permission.services as permission_services
import app.iam.user.services as user_services
from app.iam.enums import UserStatus
from app.iam.exceptions import PhoneAlreadyInUseError
from app.iam.permission.crud import PermissionCRUD, RoleCRUD
from app.iam.permission.services import PermissionService
from app.iam.user.crud import UserCRUD
from app.iam.user.models import User
from app.iam.user.query_service import UserQueryService
from app.iam.user.schemas import AdminUserUpdate
from app.iam.user.services import AdminService


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def delete(self, obj) -> None:
        pass


class _UserCRUD:
    def __init__(self, *users: SimpleNamespace) -> None:
        self.users = {user.id: user for user in users}
        self.updated: list[dict] = []

    async def get(self, session, user_id):
        return self.users.get(user_id)

    async def get_user_with_roles(self, session, user_id):
        return self.users.get(user_id)

    async def get_by_email(self, session, email):
        return next((u for u in self.users.values() if u.email == email), None)

    async def get_by_phone(self, session, phone):
        return next((u for u in self.users.values() if u.phone == phone), None)

    async def update(self, session, *, db_obj, obj_in):
        self.updated.append(obj_in)
        return db_obj


class _RoleCRUD:
    def __init__(self, *roles: SimpleNamespace) -> None:
        self.roles = {role.id: role for role in roles}
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def get(self, session, role_id):
        return self.roles.get(role_id)

    async def add_user_role(self, session, user_id, role_id):
        self.links.add((user_id, role_id))

    async def get_user_role_link(self, session, user_id, role_id):
        return (user_id, role_id) if (user_id, role_id) in self.links else None

    async def remove_user_role(self, session, link):
        self.links.discard(link)

    async def get_with_permissions(self, session, role_id):
        return self.roles.get(role_id)


class _PermissionCRUD:
    async def replace_role_permissions(self, session, role_id, permission_ids):
        pass


def _user(**fields) -> SimpleNamespace:
    defaults = dict(
        id=uuid.uuid4(),
        email=None,
        phone=None,
        full_name="Test",
        roles=[],
        is_deleted=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    return SimpleNamespace(**(defaults | fields))


@pytest.fixture
def audit(monkeypatch) -> list[dict]:
    entries: list[dict] = []

    async def record(**kwargs) -> None:
        entries.append(kwargs)

    async def no_cache(user_id) -> None:
        pass

    passthrough = SimpleNamespace(model_validate=lambda obj: obj)
    monkeypatch.setattr(user_services, "log_activity", record)
    monkeypatch.setattr(permission_services, "log_activity", record, raising=False)
    monkeypatch.setattr(UserQueryService, "invalidate_user", staticmethod(no_cache))
    monkeypatch.setattr(user_services, "UserWithRolesResponse", passthrough)
    monkeypatch.setattr(permission_services, "RoleWithPermissions", passthrough)
    return entries


def _admin_service(users: _UserCRUD, roles: _RoleCRUD | None = None) -> AdminService:
    # The fakes are test doubles; cast() says so to the type checker.
    return AdminService(
        user_crud=cast(UserCRUD, users), role_crud=cast(RoleCRUD, roles or _RoleCRUD())
    )


_ADMIN = cast(User, SimpleNamespace(id=uuid.uuid4(), email="admin@x.io", full_name="Admin"))
_SESSION = cast(AsyncSession, _Session())


async def test_a_restored_user_keeps_the_status_they_had(audit) -> None:
    user = _user(is_deleted=True, is_active=False, status=UserStatus.SUSPENDED)

    await _admin_service(_UserCRUD(user)).restore_user(_SESSION, user.id, _ADMIN)

    assert user.is_deleted is False
    assert user.status == UserStatus.SUSPENDED


async def test_an_admin_cannot_reuse_another_users_phone(audit) -> None:
    taken = _user(phone="+911111111111")
    target = _user(phone=None)
    users = _UserCRUD(taken, target)

    with pytest.raises(PhoneAlreadyInUseError):
        await _admin_service(users).update_user(
            _SESSION, target.id, AdminUserUpdate(phone="+911111111111"), _ADMIN
        )

    assert users.updated == []


async def test_an_admin_can_keep_a_users_own_phone(audit) -> None:
    user = _user(phone="+911111111111")
    users = _UserCRUD(user)

    await _admin_service(users).update_user(
        _SESSION, user.id, AdminUserUpdate(phone="+911111111111", full_name="Renamed"), _ADMIN
    )

    assert users.updated == [{"phone": "+911111111111", "full_name": "Renamed"}]


async def test_assigning_a_role_is_audited(audit) -> None:
    role = SimpleNamespace(id=uuid.uuid4(), name="admin")
    user = _user()

    await _admin_service(_UserCRUD(user), _RoleCRUD(role)).assign_roles(
        _SESSION, user.id, [role.id], _ADMIN
    )

    assert [(e["action"], e["details"]) for e in audit] == [("ASSIGN", {"roles": ["admin"]})]


async def test_removing_a_role_is_audited_only_when_one_was_removed(audit) -> None:
    role = SimpleNamespace(id=uuid.uuid4(), name="admin")
    user = _user()
    roles = _RoleCRUD(role)
    roles.links.add((user.id, role.id))
    service = _admin_service(_UserCRUD(user), roles)

    await service.remove_role(_SESSION, user.id, role.id, _ADMIN)
    await service.remove_role(_SESSION, user.id, role.id, _ADMIN)  # nothing left to remove

    assert [e["action"] for e in audit] == ["UNASSIGN"]


async def test_a_hard_delete_is_audited(audit) -> None:
    user = _user()

    await _admin_service(_UserCRUD(user)).hard_delete_user(_SESSION, user.id, _ADMIN)

    assert [(e["action"], e["details"]["permanent"]) for e in audit] == [("DELETE", True)]


async def test_setting_a_roles_permissions_is_audited(audit) -> None:
    role = SimpleNamespace(id=uuid.uuid4(), name="admin", permissions=[])
    permission_id = uuid.uuid4()
    service = PermissionService(
        role_crud=cast(RoleCRUD, _RoleCRUD(role)),
        permission_crud=cast(PermissionCRUD, _PermissionCRUD()),
    )

    await service.set_role_permissions(_SESSION, role.id, [permission_id], _ADMIN)

    assert [(e["action"], e["resource_type"], e["details"]) for e in audit] == [
        ("UPDATE", "role", {"role": "admin", "permission_ids": [str(permission_id)]})
    ]
