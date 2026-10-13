"""The ``action`` filter on ``GET /activity`` compares against the value that is stored.

``ActivityListParams.action`` is typed ``ActivityAction``, so the CRUD layer receives an enum
member, not the raw query string. While ``ActivityAction`` was a ``(str, Enum)``, Python 3.11+
rendered ``str(member)`` as ``"ActivityAction.CREATE"``; the filter upper-cased that to
``"ACTIVITYACTION.CREATE"`` and matched no row, so every filtered request came back empty with
no error. ``StrEnum`` renders the value. These tests pin that, without a database.
"""

import pytest

from app.activity.crud import ActivityLogCRUD
from app.activity.enums import ActivityAction
from app.activity.schemas import ActivityListParams


@pytest.mark.parametrize("member", list(ActivityAction))
def test_str_of_an_action_is_its_stored_value(member: ActivityAction) -> None:
    assert str(member) == member.value


def test_action_filter_binds_the_stored_value() -> None:
    params = ActivityListParams(action="CREATE")

    (clause,) = ActivityLogCRUD._build_filters(action=params.action)

    assert clause.right.value == "CREATE"


def test_actor_name_filter_matches_wildcards_literally() -> None:
    # `%` and `_` are LIKE wildcards; unescaped, a search for "50%_off" would match
    # "500 off" too. Backslash is PostgreSQL's default LIKE escape character.
    (clause,) = ActivityLogCRUD._build_filters(actor_name="50%_off\\")

    assert clause.right.value == "%50\\%\\_off\\\\%"
