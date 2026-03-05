"""
Structured Logging for Background Tasks

This module provides the TaskLogger class which automatically includes
task context (task_id, task_name, retry_count) in all log messages.

This makes it easy to:
- Track task execution through logs
- Debug production failures
- Aggregate logs by task or entity
- Correlate errors with specific task runs

Example:
    logger = TaskLogger(task_name="booking.process", task_id="123", retry_count=0)
    logger.info("Processing booking", booking_id="abc-123")
    # Output: [123] Processing booking (extra: task_id=123, booking_id=abc-123)
"""

from typing import Any, Dict, Optional
from app.core.logging import get_logger


class TaskLogger:
    """
    Structured logger for Celery tasks.

    Automatically includes task context in all log messages,
    making it easier to track and debug task execution.

    Attributes:
        task_name: Name of the Celery task
        task_id: Unique task execution ID
        retry_count: Current retry attempt number
    """

    def __init__(self, task_name: str, task_id: str, retry_count: int = 0):
        """
        Initialize task logger.

        Args:
            task_name: Name of the Celery task (e.g., "app.user.tasks.send_email")
            task_id: Unique task execution ID from Celery
            retry_count: Current retry attempt (0 for first attempt)
        """
        self.task_name = task_name
        self.task_id = task_id
        self.retry_count = retry_count
        self._logger = get_logger(task_name)

    def _build_extra(self, **kwargs) -> Dict[str, Any]:
        """
        Build extra context dict for logging.

        Combines standard task context with custom context.

        Args:
            **kwargs: Additional context to include in logs

        Returns:
            Dict with all context merged
        """
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "retry_count": self.retry_count,
            **kwargs
        }

    def _format_message(self, message: str) -> str:
        """
        Format log message with task_id prefix.

        Args:
            message: Original log message

        Returns:
            Formatted message with [task_id] prefix
        """
        return f"[{self.task_id}] {message}"

    def info(self, message: str, **extra):
        """
        Log info-level message with task context.

        Args:
            message: Log message
            **extra: Additional context fields
        """
        self._logger.info(
            self._format_message(message),
            extra=self._build_extra(**extra)
        )

    def success(self, message: str, **extra):
        """
        Log successful task completion.

        Args:
            message: Success message
            **extra: Additional context fields (e.g., result data)
        """
        self._logger.info(
            self._format_message(f"SUCCESS: {message}"),
            extra=self._build_extra(status="success", **extra)
        )

    def error(self, message: str, exc_info: bool = True, **extra):
        """
        Log error-level message with task context.

        Args:
            message: Error message
            exc_info: Include exception traceback (default: True)
            **extra: Additional context fields
        """
        self._logger.error(
            self._format_message(f"ERROR: {message}"),
            extra=self._build_extra(status="error", **extra),
            exc_info=exc_info
        )

    def warning(self, message: str, **extra):
        """
        Log warning-level message with task context.

        Args:
            message: Warning message
            **extra: Additional context fields
        """
        self._logger.warning(
            self._format_message(f"WARNING: {message}"),
            extra=self._build_extra(**extra)
        )

    def debug(self, message: str, **extra):
        """
        Log debug-level message with task context.

        Args:
            message: Debug message
            **extra: Additional context fields
        """
        self._logger.debug(
            self._format_message(message),
            extra=self._build_extra(**extra)
        )

    def add_breadcrumb(self, message: str, category: str = "task", **data):
        """
        Add Sentry breadcrumb for task execution tracing.

        Example: A task downloading a file, parsing it, and inserting to DB.
        Breadcrumbs help track the execution flow leading up to an error.

        Args:
            message: Breadcrumb message
            category: Breadcrumb category (default: "task")
            **data: Additional breadcrumb data
        """
        try:
            from app.core.sentry import add_breadcrumb as sentry_add_breadcrumb
            sentry_add_breadcrumb(
                message=message,
                category=category,
                level="info",
                data={
                    "task_id": self.task_id,
                    "task_name": self.task_name,
                    **data
                }
            )
        except Exception:
            # Don't fail task if Sentry breadcrumb fails
            pass


# Export public API
__all__ = ["TaskLogger"]
