"""ActivityLogger — fire-and-forget activity logging via Celery."""

from uuid import UUID

from .enums import ActivityAction
from .tasks import write_activity_log


class ActivityLogger:
    """Dispatch activity log entries to a background Celery task."""

    def log(
        self,
        *,
        actor_id: UUID,
        action: ActivityAction,
        resource_type: str,
        resource_id: str,
        actor_name: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Non-blocking. Fires Celery task on low_priority queue."""
        write_activity_log.delay(
            actor_id=str(actor_id),
            action=action.value,
            resource_type=resource_type,
            resource_id=str(resource_id),
            actor_name=actor_name,
            details=details,
            ip_address=ip_address,
        )


activity = ActivityLogger()
