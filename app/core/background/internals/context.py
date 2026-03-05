"""
Task Context - Unified Interface for Background Tasks

This module provides the TaskContext class, which is passed as the first
parameter to all background tasks. It provides a unified interface for:
- Structured logging with automatic task context
- Database session access (for DB tasks)
- Input validation helpers
- Result formatting
- Exception raising with clear retriable semantics
- Performance metrics and timing
- Batch operation utilities

TaskContext makes tasks:
- Easier to write (less boilerplate)
- Easier to test (mock the context)
- Easier to debug (structured logging)
- More consistent (standard patterns)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, AsyncGenerator
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from .logging import TaskLogger
from .monitoring import TaskMetrics, Timer, StatsCounter
from .exceptions import (
    TaskValidationError,
    TaskNotFoundError,
    TaskConfigurationError,
)


@dataclass
class TaskContext:
    """
    Unified context object passed to all background tasks.

    Provides utilities for logging, database access, validation,
    metrics, and error handling with consistent patterns.

    Attributes:
        task: Celery task instance
        task_id: Unique task execution ID
        retry_count: Current retry attempt number
        session: Database session (only for DB tasks)
        _logger: Task logger instance (lazy loaded)
        _metrics: Task metrics instance (lazy loaded)
    """

    task: Any  # Celery Task instance
    task_id: str
    retry_count: int
    session: Optional[AsyncSession] = None
    _logger: Optional[TaskLogger] = None
    _metrics: Optional[TaskMetrics] = None
    _timers: Dict[str, Timer] = field(default_factory=dict)

    @property
    def logger(self) -> TaskLogger:
        """
        Get task logger with automatic context.

        Lazy loaded on first access.

        Returns:
            TaskLogger instance
        """
        if self._logger is None:
            self._logger = TaskLogger(
                task_name=self.task.name,
                task_id=self.task_id,
                retry_count=self.retry_count
            )
        return self._logger

    @property
    def metrics(self) -> TaskMetrics:
        """
        Get task metrics tracker.

        Lazy loaded on first access.

        Returns:
            TaskMetrics instance
        """
        if self._metrics is None:
            self._metrics = TaskMetrics(
                task_name=self.task.name,
                task_id=self.task_id,
                retry_count=self.retry_count
            )
        return self._metrics

    # ==================== Logging Methods ====================

    def log_info(self, message: str, **extra):
        """
        Log info-level message.

        Args:
            message: Log message
            **extra: Additional context fields
        """
        self.logger.info(message, **extra)

    def log_success(self, message: str, **extra):
        """
        Log successful task completion.

        Args:
            message: Success message
            **extra: Additional context (e.g., result data)
        """
        self.logger.success(message, **extra)

    def log_error(self, message: str, exc_info: bool = True, **extra):
        """
        Log error-level message.

        Args:
            message: Error message
            exc_info: Include exception traceback
            **extra: Additional context fields
        """
        self.logger.error(message, exc_info=exc_info, **extra)

    def log_warning(self, message: str, **extra):
        """
        Log warning-level message.

        Args:
            message: Warning message
            **extra: Additional context fields
        """
        self.logger.warning(message, **extra)

    def log_debug(self, message: str, **extra):
        """
        Log debug-level message.

        Args:
            message: Debug message
            **extra: Additional context fields
        """
        self.logger.debug(message, **extra)

    def log_progress(self, **metrics):
        """
        Log progress metrics for long-running tasks.

        Args:
            **metrics: Progress metrics (processed=10, failed=2, etc.)
        """
        self.logger.info(
            f"Progress update",
            **metrics
        )

    # ==================== Result Helpers ====================

    def success_result(self, **data) -> Dict[str, Any]:
        """
        Create standardized success result dictionary.

        Args:
            **data: Additional result data

        Returns:
            Dict with status="success" and task_id

        Example:
            return ctx.success_result(user_id=123, email_sent=True)
        """
        return {
            "status": "success",
            "task_id": self.task_id,
            **data
        }

    def error_result(self, error: str, **data) -> Dict[str, Any]:
        """
        Create standardized error result dictionary.

        Args:
            error: Error message
            **data: Additional error context

        Returns:
            Dict with status="error" and task_id

        Example:
            return ctx.error_result("User not found", user_id=123)
        """
        return {
            "status": "error",
            "task_id": self.task_id,
            "error": error,
            **data
        }

    # ==================== Validation Helpers ====================

    def validate_uuid(self, value: str, field_name: str = "id") -> UUID:
        """
        Validate and convert UUID string.

        Raises TaskValidationError (non-retriable) on invalid format.

        Args:
            value: UUID string to validate
            field_name: Name of the field (for error messages)

        Returns:
            UUID object

        Raises:
            TaskValidationError: If UUID format is invalid

        Example:
            provider_uuid = ctx.validate_uuid(provider_id, "provider_id")
        """
        try:
            return UUID(value)
        except (ValueError, TypeError, AttributeError) as e:
            raise TaskValidationError(
                f"Invalid UUID format for {field_name}: {value}",
                field=field_name,
                value=value
            ) from e

    # ==================== Exception Helpers ====================

    def not_found_error(self, message: str, **context):
        """
        Raise TaskNotFoundError (non-retriable).

        Args:
            message: Error message
            **context: Additional context (entity_id, entity_type, etc.)

        Raises:
            TaskNotFoundError

        Example:
            if not user:
                raise ctx.not_found_error("User not found", user_id=123)
        """
        raise TaskNotFoundError(message, **context)

    def validation_error(self, message: str, **context):
        """
        Raise TaskValidationError (non-retriable).

        Args:
            message: Error message
            **context: Additional context (field, value, etc.)

        Raises:
            TaskValidationError

        Example:
            if age < 0:
                raise ctx.validation_error("Age must be positive", age=age)
        """
        raise TaskValidationError(message, **context)

    def config_error(self, message: str, **context):
        """
        Raise TaskConfigurationError (non-retriable).

        Args:
            message: Error message
            **context: Additional context

        Raises:
            TaskConfigurationError

        Example:
            if not api_key:
                raise ctx.config_error("Missing API key")
        """
        raise TaskConfigurationError(message, **context)

    # ==================== Monitoring/Metrics Helpers ====================

    def start_timer(self, name: str) -> Timer:
        """
        Start a named timer for measuring operation duration.

        Args:
            name: Timer name

        Returns:
            Timer instance

        Example:
            ctx.start_timer("database_query")
            # ... perform query ...
            duration = ctx.end_timer("database_query")
        """
        timer = Timer(name)
        self._timers[name] = timer
        return timer

    def end_timer(self, name: str) -> Optional[float]:
        """
        Stop a named timer and return duration.

        Args:
            name: Timer name

        Returns:
            Duration in seconds, or None if timer not found

        Example:
            duration = ctx.end_timer("database_query")
            ctx.log_info(f"Query took {duration:.2f}s")
        """
        timer = self._timers.get(name)
        if timer:
            duration = timer.stop()
            self.log_debug(f"Timer '{name}' completed", duration=duration)
            return duration
        return None

    def increment_metric(self, name: str, value: int = 1):
        """
        Increment a custom metric counter.

        Args:
            name: Metric name
            value: Amount to increment

        Example:
            ctx.increment_metric("emails_sent")
            ctx.increment_metric("processing_errors", 2)
        """
        self.metrics.add_custom_metric(name, value)

    # ==================== Batch Operation Helpers ====================

    def create_stats_counter(self) -> StatsCounter:
        """
        Create a statistics counter for batch operations.

        Returns:
            StatsCounter instance

        Example:
            stats = ctx.create_stats_counter()
            for item in items:
                if process(item):
                    stats.increment("processed")
                else:
                    stats.increment("failed")
            return ctx.success_result(**stats.to_dict())
        """
        return StatsCounter()

    async def iter_batches(
        self,
        items: Optional[List[Any]],
        crud: Any,
        batch_size: int = 20,
        all_items_query: bool = False
    ) -> AsyncGenerator[List[Any], None]:
        """
        Iterate over items in batches.

        This async generator is safe to exit early (via `break` or exception).
        The database session is managed at the task level, so partial iteration
        does not cause resource leaks.

        Args:
            items: List of items to batch, or None to fetch all
            crud: CRUD object with get_multi method
            batch_size: Number of items per batch
            all_items_query: If True and items is None, fetch all from DB

        Yields:
            List of items in each batch

        Note:
            - When `items` is provided, it slices the in-memory list (no DB calls)
            - When `all_items_query=True`, it fetches from DB using `crud.get_multi()`
            - Early exit (break) is safe - the session is managed by DatabaseTask
            - Always call `await ctx.commit_batch()` after processing each batch

        Example:
            async for batch in ctx.iter_batches(provider_ids, provider_crud, batch_size=50):
                for provider in batch:
                    # Process provider
                    pass
                await ctx.commit_batch()
        """
        if items:
            # Batch provided list
            for i in range(0, len(items), batch_size):
                yield items[i:i + batch_size]
        elif all_items_query and self.session:
            # Fetch all from database in batches
            skip = 0
            while True:
                batch = await crud.get_multi(
                    self.session,
                    skip=skip,
                    limit=batch_size
                )
                if not batch:
                    break
                yield batch
                skip += batch_size
        else:
            # No items to iterate
            return

    async def commit_batch(self):
        """
        Commit current batch to database.

        Example:
            async for batch in ctx.iter_batches(...):
                # Process batch
                await ctx.commit_batch()
        """
        if self.session:
            await self.session.commit()
            self.log_debug("Batch committed")


# Export public API
__all__ = ["TaskContext"]
