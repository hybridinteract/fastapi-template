"""Activity logging adapter — no-op when app.activity is absent."""

from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


class ActivityAction:
    """The actions iam records. Each value is a member of ``app.activity``'s ``ActivityAction``."""

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    RESTORE = "RESTORE"
    ASSIGN = "ASSIGN"
    UNASSIGN = "UNASSIGN"


async def log_activity(
    actor_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_name: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log activity if app.activity is available; no-op when it is absent.

    Never raises — an audit write must not fail the request it records — but a failure is logged
    as a warning, never swallowed: a silent failure here drops every audit entry unnoticed.
    """
    try:
        from app.activity import ActivityAction as ActivityLogAction
        from app.activity import activity
    except ImportError:
        return
    try:
        activity.log(
            actor_id=actor_id,
            action=ActivityLogAction(action),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_name=actor_name,
            ip_address=ip_address,
            details=details,
        )
    except Exception:
        logger.warning(
            "Activity log dropped: %s %s:%s", action, resource_type, resource_id, exc_info=True
        )
