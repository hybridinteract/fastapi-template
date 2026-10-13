"""Changing the password signs out every session.

Before, a refresh token stolen before the change kept working after it. Now every refresh token is
revoked in the same transaction as the new password, so the two cannot be split by a failure.

These run without a database: the service gets in-memory fakes that record the order of writes.
"""

import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.iam.auth.providers.email_password as email_password
from app.iam.auth.crud import RefreshTokenCRUD
from app.iam.auth.exceptions import InvalidCredentialsError
from app.iam.auth.providers.email_password import EmailPasswordService
from app.iam.auth.schemas import ChangePasswordRequest
from app.iam.auth.services import TokenService
from app.iam.auth.tokens import get_password_hash
from app.iam.user.crud import UserCRUD
from app.iam.user.models import User
from app.iam.user.query_service import UserQueryService


class _Session:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")


class _RefreshTokenCRUD:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def revoke_all_user_tokens(self, session, user_id) -> int:
        self.events.append("revoke")
        return 2


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch) -> None:
    async def noop(*args, **kwargs) -> None:
        pass

    monkeypatch.setattr(email_password, "log_activity", noop)
    monkeypatch.setattr(UserQueryService, "invalidate_user", staticmethod(noop))


def _service(events: list[str]) -> EmailPasswordService:
    # The fakes are test doubles; cast() says so to the type checker.
    return EmailPasswordService(
        user_crud=cast(UserCRUD, None),
        token_service=cast(TokenService, None),
        refresh_token_crud=cast(RefreshTokenCRUD, _RefreshTokenCRUD(events)),
    )


def _user() -> User:
    return cast(
        User,
        SimpleNamespace(
            id=uuid.uuid4(),
            email="a@x.io",
            full_name="A",
            hashed_password=get_password_hash("old-password-1"),
            updated_at=None,
        ),
    )


async def test_every_session_is_revoked_in_the_same_transaction() -> None:
    events: list[str] = []
    request = ChangePasswordRequest(
        current_password="old-password-1", new_password="new-password-2"
    )

    await _service(events).change_password(cast(AsyncSession, _Session(events)), _user(), request)

    assert events == ["revoke", "commit"]


async def test_a_wrong_current_password_revokes_nothing() -> None:
    events: list[str] = []
    request = ChangePasswordRequest(
        current_password="wrong-password", new_password="new-password-2"
    )

    with pytest.raises(InvalidCredentialsError):
        await _service(events).change_password(
            cast(AsyncSession, _Session(events)), _user(), request
        )

    assert events == []
