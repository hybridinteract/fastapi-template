"""iam's audit entries reach ``app.activity``, and a failed write is logged, not swallowed.

``log_activity`` used to hand ``activity.log`` plain strings, which it reads ``.value`` from. Every
call raised, the adapter swallowed it, and no iam action — sign-in, user change, role change — was
ever recorded. These run without Celery: the task's ``delay`` is replaced.
"""

import uuid

import pytest

import app.activity.tasks as activity_tasks
import app.iam.auth.activity as adapter
from app.activity import ActivityAction as ActivityLogAction
from app.iam.auth.activity import ActivityAction, log_activity


class _Logger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, msg, *args, **kwargs) -> None:
        self.warnings.append(msg % args)


@pytest.fixture
def dispatched(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(activity_tasks.write_activity_log, "delay", lambda **kw: calls.append(kw))
    return calls


def test_every_iam_action_is_an_activity_action() -> None:
    values = [v for k, v in vars(ActivityAction).items() if k.isupper()]

    assert values
    for value in values:
        ActivityLogAction(value)  # raises ValueError for an action app.activity does not know


async def test_an_iam_action_is_dispatched(dispatched) -> None:
    await log_activity(
        actor_id=uuid.uuid4(), action=ActivityAction.ASSIGN, resource_type="user", resource_id="u1"
    )

    assert [call["action"] for call in dispatched] == ["ASSIGN"]


async def test_a_failed_write_is_logged_and_does_not_raise(monkeypatch) -> None:
    def broker_down(**kwargs):
        raise RuntimeError("broker down")

    logger = _Logger()
    monkeypatch.setattr(activity_tasks.write_activity_log, "delay", broker_down)
    monkeypatch.setattr(adapter, "logger", logger)

    await log_activity(
        actor_id=uuid.uuid4(), action=ActivityAction.UPDATE, resource_type="user", resource_id="u1"
    )

    assert logger.warnings == ["Activity log dropped: UPDATE user:u1"]
