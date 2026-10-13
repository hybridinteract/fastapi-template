"""Only an ``active`` user signs in.

``status`` and ``is_active`` are independent: ``PATCH /users/{id}`` with ``{"status": "inactive"}``
leaves ``is_active`` true. The gates used to refuse only ``suspended`` and
``pending_verification``, so an admin who marked someone ``inactive`` had not locked them out.
The same rule runs at sign-in (``assert_user_active``), on every request (``get_current_user``)
and on token refresh; this pins the sign-in gate, which every provider calls.
"""

from types import SimpleNamespace
from typing import cast

import pytest

from app.iam.auth.exceptions import InactiveUserError
from app.iam.auth.services import assert_user_active
from app.iam.enums import UserStatus
from app.iam.user.models import User


def _user(status: UserStatus) -> User:
    return cast(User, SimpleNamespace(is_active=True, is_deleted=False, status=status))


@pytest.mark.parametrize("status", [s for s in UserStatus if s is not UserStatus.ACTIVE])
def test_every_status_but_active_is_refused(status: UserStatus) -> None:
    with pytest.raises(InactiveUserError):
        assert_user_active(_user(status))


def test_an_active_user_passes() -> None:
    assert assert_user_active(_user(UserStatus.ACTIVE)) is None
