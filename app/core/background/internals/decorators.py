"""
Task Decorators

This module provides easy-to-use decorators for creating Celery tasks
with best practices built-in:
- Automatic retry configuration
- TaskContext injection
- Session management (for DB tasks)
- Structured logging and metrics

Two main decorators:
1. @simple_task - For tasks without database operations
2. @db_task - For tasks with async database operations (includes batch utilities)

Example:
    @simple_task(name="app.user.tasks.send_email", retry_policy="high_priority")
    def send_email(ctx: TaskContext, email: str):
        ctx.log_info(f"Sending email to {email}")
        # ... send email ...
        return ctx.success_result(email_sent=True)
"""

from functools import wraps
from typing import Callable, Any, Optional

# Import celery_app from parent background directory
from ..celery_app import celery_app
from .base import BaseTask, DatabaseTask
from .retry import get_retry_policy


def simple_task(
    name: str,
    retry_policy: str = "standard",
    queue: str = "default",
    **celery_kwargs
) -> Callable:
    """
    Decorator for simple tasks without database dependencies.

    Creates a Celery task with:
    - Automatic TaskContext injection
    - Predefined retry policy
    - Queue-based priority routing
    - Structured logging
    - Metrics tracking

    Args:
        name: Full task name (e.g., "app.user.tasks.send_email")
        retry_policy: Name of retry policy from retry.py (default: "standard")
        queue: Queue name for priority routing (default: "default")
            Options: "default", "high_priority", "low_priority"
        **celery_kwargs: Additional Celery task configuration

    Returns:
        Decorated task function

    Example:
        # High priority task (OTP, password reset)
        @simple_task(
            name="app.user.tasks.send_otp",
            retry_policy="aggressive",
            queue="high_priority"
        )
        def send_otp(ctx: TaskContext, phone: str, code: str):
            ctx.log_info(f"Sending OTP to {phone}")
            result = send_sms(phone, f"Your code: {code}")
            return ctx.success_result(sent=True)

        # Low priority task (cleanup, reports)
        @simple_task(
            name="app.reports.tasks.generate_monthly",
            queue="low_priority"
        )
        def generate_monthly_report(ctx: TaskContext, month: str):
            ctx.log_info(f"Generating report for {month}")
            # ... generate report
            return ctx.success_result(generated=True)
    """
    # Get retry configuration
    retry_config = get_retry_policy(retry_policy)

    def decorator(func: Callable) -> Callable:
        @celery_app.task(
            name=name,
            base=BaseTask,
            bind=True,
            queue=queue,
            **retry_config,
            **celery_kwargs
        )
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # BaseTask.__call__ handles TaskContext injection
            return func(*args, **kwargs)

        return wrapper

    return decorator


def db_task(
    name: str,
    retry_policy: str = "standard",
    queue: str = "default",
    **celery_kwargs
) -> Callable:
    """
    Decorator for tasks requiring database access.

    Creates a Celery task with:
    - Automatic TaskContext injection with database session
    - Event loop management (reuses worker's loop)
    - Automatic commit on success
    - Automatic rollback on failure
    - Queue-based priority routing
    - Predefined retry policy
    - Structured logging and metrics

    The decorated function MUST be async and will receive a TaskContext
    with `session` populated.

    Args:
        name: Full task name (e.g., "app.booking.tasks.process_booking")
        retry_policy: Name of retry policy from retry.py (default: "standard")
        queue: Queue name for priority routing (default: "default")
            Options: "default", "high_priority", "low_priority"
        **celery_kwargs: Additional Celery task configuration

    Returns:
        Decorated async task function

    Example:
        # High priority booking confirmation
        @db_task(
            name="app.booking.tasks.confirm_booking",
            retry_policy="standard",
            queue="high_priority"
        )
        async def confirm_booking(ctx: TaskContext, booking_id: str):
            ctx.log_info(f"Confirming booking {booking_id}")
            booking = await booking_crud.get(ctx.session, booking_id)
            # ... update booking status
            return ctx.success_result(booking_id=booking_id)

        # Low priority profile calculation
        @db_task(
            name="app.provider.tasks.update_profile",
            queue="low_priority"
        )
        async def update_profile_completion(ctx: TaskContext, provider_id: str):
            provider_uuid = ctx.validate_uuid(provider_id, "provider_id")
            provider = await provider_crud.get(ctx.session, provider_uuid)
            if not provider:
                raise ctx.not_found_error(f"Provider not found")
            await calculate_completion(ctx.session, provider)
            return ctx.success_result(provider_id=provider_id)
    """
    # Get retry configuration
    retry_config = get_retry_policy(retry_policy)

    def decorator(func: Callable) -> Callable:
        @celery_app.task(
            name=name,
            base=DatabaseTask,
            bind=True,
            queue=queue,
            **retry_config,
            **celery_kwargs
        )
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # DatabaseTask.__call__ handles event loop + session management
            return func(*args, **kwargs)

        return wrapper

    return decorator

# Export public API
__all__ = [
    "simple_task",
    "db_task",
]
