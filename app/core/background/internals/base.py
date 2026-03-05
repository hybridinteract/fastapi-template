"""
Base Task Classes

This module provides base classes for all Celery tasks with built-in:
- TaskContext injection
- Automatic metrics tracking
- Standard error handling
- Sentry integration
- Database session management (for DatabaseTask)
- Batch operation support

Hierarchy:
    celery.Task
    └── BaseTask (simple tasks, no DB)
        └── DatabaseTask (async DB operations)
"""

from typing import Any, Callable
from celery import Task
from app.core.logging import get_logger
from .context import TaskContext
from .session import get_task_session
from .event_loop import run_with_event_loop
from .exceptions import TaskException

logger = get_logger(__name__)


class BaseTask(Task):
    """
    Base class for all simple Celery tasks (no database operations).

    Provides:
    - Automatic TaskContext injection as first parameter
    - Standard failure handling with Sentry integration
    - Metrics tracking
    - Structured logging

    Tasks inheriting from this class will receive a TaskContext
    as their first parameter.

    Example:
        @celery_app.task(base=BaseTask, bind=True)
        def my_task(self, ctx: TaskContext, param1, param2):
            ctx.log_info("Processing task")
            # ... task logic ...
            return ctx.success_result(processed=True)
    """

    def __call__(self, *args, **kwargs):
        """
        Override to inject TaskContext before task execution.

        This is called when the task is executed, and we inject
        the TaskContext as the first argument.
        """
        # Create TaskContext
        ctx = TaskContext(
            task=self,
            task_id=self.request.id,
            retry_count=self.request.retries
        )

        # Call the actual task function with context injected
        try:
            ctx.log_debug(f"Task started", **kwargs)
            result = self.run(ctx, *args, **kwargs)
            ctx.metrics.mark_success()
            return result
        except Exception as exc:
            ctx.metrics.mark_failure(exc)
            ctx.log_error(f"Task failed: {exc}")
            raise

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails after all retries.

        Provides standardized failure handling and Sentry integration.

        Args:
            exc: The exception raised by the task
            task_id: Unique id of the failed task
            args: Original arguments for the task
            kwargs: Original keyword arguments for the task
            einfo: ExceptionInfo instance with traceback
        """
        logger.error(
            f"Task {self.name} failed permanently: {exc}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "error_type": type(exc).__name__,
                "retriable": getattr(exc, "retriable", True) if isinstance(exc, TaskException) else True
            },
            exc_info=True
        )

        # Sentry will automatically capture this via exception handlers
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task is retried.

        Args:
            exc: The exception that caused the retry
            task_id: Unique id of the task
            args: Original arguments for the task
            kwargs: Original keyword arguments for the task
            einfo: ExceptionInfo instance
        """
        logger.warning(
            f"Task {self.name} retrying due to: {exc}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "error_type": type(exc).__name__,
                "retry_count": self.request.retries
            }
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)


class DatabaseTask(BaseTask):
    """
    Base class for tasks requiring database access.

    Automatically manages:
    - Async database session lifecycle
    - Event loop reuse (prevents "attached to different loop" errors)
    - Automatic commit on success
    - Automatic rollback on failure

    The task function receives a TaskContext with `session` populated.

    Example:
        @celery_app.task(base=DatabaseTask, bind=True)
        async def my_db_task(ctx: TaskContext, user_id: str):
            ctx.log_info("Fetching user")
            user = await user_crud.get(ctx.session, user_id)
            # Session auto-commits on success, auto-rollbacks on error
            return ctx.success_result(user_id=str(user.id))
    """

    def __call__(self, *args, **kwargs):
        """
        Override to wrap task execution with async session management.

        This wraps the task function in event loop and session context.
        """
        # Wrap in event loop and session management
        return run_with_event_loop(self._execute_with_session, *args, **kwargs)

    async def _execute_with_session(self, *args, **kwargs):
        """
        Execute task with database session.

        This method:
        1. Creates async database session
        2. Creates TaskContext with session
        3. Executes task function
        4. Commits on success
        5. Rollbacks on error
        """
        async with get_task_session() as session:
            # Create TaskContext with session
            ctx = TaskContext(
                task=self,
                task_id=self.request.id,
                retry_count=self.request.retries,
                session=session
            )

            try:
                ctx.log_debug(f"DB task started", **kwargs)

                # Call the actual task function
                result = await self.run(ctx, *args, **kwargs)

                # Commit the session
                await session.commit()
                ctx.log_debug("Session committed successfully")

                ctx.metrics.mark_success()
                return result

            except Exception as exc:
                # Rollback handled by get_task_session context manager
                ctx.metrics.mark_failure(exc)

                # Check if error should be retried
                from .exceptions import is_retriable_error

                if not is_retriable_error(exc):
                    ctx.log_error(
                        f"DB task failed with non-retriable error: {exc}",
                        error_type=type(exc).__name__,
                        retriable=False
                    )
                    # Don't retry - fail permanently
                    raise
                else:
                    ctx.log_error(
                        f"DB task failed (will retry): {exc}",
                        error_type=type(exc).__name__,
                        retriable=True
                    )
                    # Let Celery retry according to retry policy
                    raise


# Export public API
__all__ = [
    "BaseTask",
    "DatabaseTask",
]
