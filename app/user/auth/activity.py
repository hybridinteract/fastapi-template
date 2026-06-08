"""Activity logging adapter — no-op when app.activity is absent."""

from typing import Any, Optional
from uuid import UUID


class ActivityAction:
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"


async def log_activity(
    actor_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Log activity if app.activity is available; silently no-op otherwise."""
    try:
        from app.activity import activity
        activity.log(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_name=actor_name,
            ip_address=ip_address,
            details=details,
        )
    except (ImportError, Exception):
        pass
