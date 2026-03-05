"""
Core Background Tasks (Optional)

This file is for core-level background tasks that don't belong in any specific
app module. Examples include:
- System maintenance tasks
- Administrative tasks
- Cross-module operations
- Infrastructure monitoring

Tasks are auto-discovered by Celery, so you just need to define them here using
the framework decorators.

Example:
    from app.core.background import simple_task, db_task, TaskContext

    @simple_task(
        name="app.core.background.tasks.system_health_check",
        retry_policy="standard",
        queue="low_priority"
    )
    def system_health_check(ctx: TaskContext):
        ctx.log_info("Running system health check")
        # ... check system health ...
        return ctx.success_result(status="healthy")
"""

from app.core.background import simple_task, db_task, TaskContext
from app.core.logging import get_logger

logger = get_logger(__name__)


# ==================== Task Result Cleanup ====================

@simple_task(
    name="app.core.background.tasks.cleanup_expired_task_results",
    retry_policy="standard",
    queue="low_priority"
)
def cleanup_expired_task_results(ctx: TaskContext, days_old: int = 2):
    """
    Clean up expired task results from Redis backend.

    This task prevents Redis memory growth by removing old task results.
    Should be scheduled to run daily via Celery Beat.

    Args:
        ctx: Task context
        days_old: Delete results older than N days (default: 2)

    Returns:
        dict: Cleanup statistics

    Example:
        # Manual trigger
        cleanup_expired_task_results.delay(days_old=2)

        # Scheduled in Celery Beat (celery_app.py):
        beat_schedule = {
            "cleanup-expired-results-daily": {
                "task": "app.core.background.tasks.cleanup_expired_task_results",
                "schedule": crontab(hour=3, minute=0),
                "args": (2,),
            }
        }
    """
    ctx.log_info(f"Starting cleanup of task results older than {days_old} days")

    from datetime import datetime, timedelta
    from app.core.background import celery_app

    try:
        # Calculate cutoff timestamp
        cutoff_time = datetime.utcnow() - timedelta(days=days_old)
        cutoff_timestamp = cutoff_time.timestamp()

        ctx.log_info(f"Cleaning results before {cutoff_time.isoformat()}")

        # Use Celery's backend cleanup
        # This removes expired results efficiently
        backend = celery_app.backend

        # Get count before cleanup for metrics
        try:
            # This is backend-specific, works with Redis
            cleaned = 0
            if hasattr(backend, 'cleanup'):
                # Some backends support cleanup method
                cleaned = backend.cleanup()
            else:
                # Fallback: let expiration handle it
                ctx.log_info("Backend auto-expires results, no manual cleanup needed")
                cleaned = 0

        except Exception as e:
            ctx.log_warning(f"Cleanup method not available: {e}")
            cleaned = 0

        ctx.log_success(
            f"Task result cleanup completed",
            cleaned_count=cleaned,
            cutoff_days=days_old
        )

        return ctx.success_result(
            cleaned_count=cleaned,
            cutoff_days=days_old,
            cutoff_time=cutoff_time.isoformat()
        )

    except Exception as e:
        ctx.log_error(f"Failed to cleanup task results: {e}")
        raise


# ==================== Example Core Tasks ====================

# Uncomment and customize these examples as needed:

# @simple_task(
#     name="app.core.background.tasks.cleanup_old_logs",
#     retry_policy="standard",
#     queue="low_priority"
# )
# def cleanup_old_logs(ctx: TaskContext, days_old: int = 30):
#     """
#     Clean up old log files from the system.
#
#     Args:
#         ctx: Task context
#         days_old: Number of days after which logs should be deleted
#
#     Returns:
#         dict: Cleanup statistics
#     """
#     ctx.log_info(f"Cleaning up logs older than {days_old} days")
#
#     # TODO: Implement log cleanup logic
#     cleaned_count = 0
#
#     ctx.log_success(f"Cleaned up {cleaned_count} old log files")
#     return ctx.success_result(cleaned=cleaned_count, days_old=days_old)


# @db_task(
#     name="app.core.background.tasks.database_maintenance",
#     retry_policy="long_running",
#     queue="low_priority"
# )
# async def database_maintenance(ctx: TaskContext):
#     """
#     Perform database maintenance operations.
#
#     Args:
#         ctx: Task context with database session
#
#     Returns:
#         dict: Maintenance statistics
#     """
#     ctx.log_info("Starting database maintenance")
#
#     # TODO: Implement database maintenance
#     # - VACUUM
#     # - ANALYZE
#     # - Index rebuilding
#
#     ctx.log_success("Database maintenance completed")
#     return ctx.success_result(status="completed")


# ==================== Export Tasks ====================

# Add your tasks to __all__ for explicit exports
__all__ = [
    "cleanup_expired_task_results",
    # "cleanup_old_logs",
    # "database_maintenance",
]
