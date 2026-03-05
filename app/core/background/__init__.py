"""
Background Task Framework

A comprehensive framework for Celery background tasks with:
- Standardized task decorators (@simple_task, @db_task)
- Automatic session and event loop management
- Structured logging with task context
- Performance metrics and monitoring
- Testing utilities

Usage:
    from app.core.background import simple_task, TaskContext

    @simple_task(name="app.user.tasks.send_email", retry_policy="high_priority")
    def send_email(ctx: TaskContext, email: str):
        ctx.log_info(f"Sending email to {email}")
        # ... send email ...
        return ctx.success_result(email_sent=True)

For database tasks:
    from app.core.background import db_task, TaskContext

    @db_task(name="app.booking.tasks.process", retry_policy="standard")
    async def process_booking(ctx: TaskContext, booking_id: str):
        ctx.log_info(f"Processing booking {booking_id}")
        booking = await booking_crud.get(ctx.session, booking_id)
        # ... process booking ...
        # Auto-commit on success
        return ctx.success_result(booking_id=booking_id)

For batch operations (use @db_task with batch utilities):
    @db_task(name="app.provider.tasks.bulk_update", retry_policy="long_running", queue="low_priority")
    async def bulk_update_profiles(ctx: TaskContext, provider_ids: list[str]):
        stats = ctx.create_stats_counter()
        async for batch in ctx.iter_batches(provider_ids, provider_crud, batch_size=50):
            for provider in batch:
                # process provider
                stats.increment("processed")
            await ctx.commit_batch()
        return ctx.success_result(**stats.to_dict())

Optional extras (import separately):
    from app.core.background.extras import CircuitBreaker, CircuitBreakerOpen
"""

# Import celery_app from this module
from .celery_app import celery_app

# Re-export everything from internals for public API
from .internals import (
    # Primary decorators
    simple_task,
    db_task,

    # Core classes
    TaskContext,

    # Exceptions
    TaskException,
    TaskValidationError,
    TaskNotFoundError,
    TaskConfigurationError,
    TaskTimeoutError,
    NON_RETRIABLE_EXCEPTIONS,
    is_retriable_error,

    # Testing
    TaskTestContext,
    mock_task_session,
    run_task_sync,

    # Monitoring
    TaskMetrics,
    Timer,
    StatsCounter,
    log_metric,

    # Advanced - for special cases
    BaseTask,
    DatabaseTask,
    RETRY_POLICIES,
    get_retry_policy,
    get_task_session,
    TaskSessionManager,
    run_with_event_loop,
    get_or_create_event_loop,
    TaskLogger,
)


# Public API - what users should import
__all__ = [
    # Celery app
    "celery_app",

    # Primary decorators
    "simple_task",
    "db_task",

    # Core classes
    "TaskContext",

    # Exceptions
    "TaskException",
    "TaskValidationError",
    "TaskNotFoundError",
    "TaskConfigurationError",
    "TaskTimeoutError",
    "is_retriable_error",
    "NON_RETRIABLE_EXCEPTIONS",

    # Testing
    "TaskTestContext",
    "mock_task_session",
    "run_task_sync",

    # Monitoring
    "TaskMetrics",
    "Timer",
    "StatsCounter",
    "log_metric",

    # Advanced - for special cases
    "BaseTask",
    "DatabaseTask",
    "RETRY_POLICIES",
    "get_retry_policy",
    "get_task_session",
    "TaskSessionManager",
    "run_with_event_loop",
    "get_or_create_event_loop",
    "TaskLogger",
]


# Module version
__version__ = "1.1.0"
