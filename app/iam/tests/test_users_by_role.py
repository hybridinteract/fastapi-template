"""The users-by-role picker returns options, not profiles.

``GET /users/me/by-role/{role}`` is authenticated but ungated, as a picker is
(``.claude/rules/permissions.md`` rule 9), and sign-up is public. It used to return each user's
email, phone, superuser flag and last login — so any signed-in stranger could list them, including
for ``developer_admin``. It now returns id, name and avatar only.
"""

import uuid
from datetime import UTC, datetime
from typing import cast

from app.iam.enums import UserStatus
from app.iam.user.query_service import UserQueryService
from app.iam.user.routes import get_users_by_role
from app.iam.user.schemas import UserResponse


class _QueryService:
    async def get_active_users_by_role(self, session, role):
        now = datetime.now(UTC)
        return [
            UserResponse(
                id=uuid.uuid4(),
                email="root@x.io",
                full_name="Root",
                phone="+911111111111",
                status=UserStatus.ACTIVE,
                email_verified=True,
                is_active=True,
                is_superuser=True,
                last_login_at=now,
                created_at=now,
                updated_at=now,
            )
        ]


async def test_the_picker_returns_no_contact_details_or_access_flags() -> None:
    options = await get_users_by_role(
        role="developer_admin",
        session=None,  # type: ignore[arg-type]
        current_user=None,  # type: ignore[arg-type]
        query_service=cast(UserQueryService, _QueryService()),
    )

    assert [set(option.model_dump()) for option in options] == [{"id", "full_name", "avatar_url"}]
