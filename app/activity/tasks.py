"""Background Celery task for writing activity logs."""

from app.core.background import db_task, TaskContext
from .models import ActivityLog


@db_task(
    name="app.activity.tasks.write_activity_log",
    retry_policy="standard",
    queue="low_priority",
)
async def write_activity_log(
    ctx: TaskContext,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_name: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
):
    """Write a single activity log entry. Auto-committed by @db_task."""
    actor_uuid = ctx.validate_uuid(actor_id, "actor_id")

    entry = ActivityLog(
        actor_id=actor_uuid,
        actor_name=actor_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    ctx.session.add(entry)
    ctx.log_info(
        f"Activity logged: {action} {resource_type}:{resource_id}",
        actor_id=actor_id,
    )
    return ctx.success_result(activity_id=str(entry.id))
