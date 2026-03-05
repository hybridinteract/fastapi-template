"""
Testing Utilities for Background Tasks

This module provides utilities to make testing Celery tasks easier:
- Mock TaskContext for unit tests
- Async task execution in synchronous tests
- Logging assertion helpers
- Session mocking utilities

Example:
    async def test_my_task():
        ctx = TaskTestContext(task_id="test-123")
        result = await my_task(ctx, param1="value")
        assert result["status"] == "success"
        ctx.assert_logged_info()
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock
from uuid import UUID

from .context import TaskContext
from .monitoring import StatsCounter


@dataclass
class TaskTestContext:
    """
    Mock TaskContext for testing background tasks.

    Provides the same interface as TaskContext but stores
    log calls and metrics for assertion in tests.

    Example:
        ctx = TaskTestContext(task_id="test-123")
        my_task(ctx, user_id=123)
        ctx.assert_logged_success()
        assert ctx.info_logs[0]["message"] == "Processing user"
    """
    task_id: str = "test-task-id"
    retry_count: int = 0
    session: Optional[Any] = None

    # Mock task instance
    task: Any = field(default_factory=lambda: MagicMock(name="mock_task"))

    # Logged messages storage
    info_logs: List[Dict[str, Any]] = field(default_factory=list)
    success_logs: List[Dict[str, Any]] = field(default_factory=list)
    error_logs: List[Dict[str, Any]] = field(default_factory=list)
    warning_logs: List[Dict[str, Any]] = field(default_factory=list)
    debug_logs: List[Dict[str, Any]] = field(default_factory=list)

    # Metrics storage
    _timers: Dict[str, float] = field(default_factory=dict)
    _metrics: Dict[str, Any] = field(default_factory=dict)

    def log_info(self, message: str, **extra):
        """Mock log_info - stores call for assertion."""
        self.info_logs.append({"message": message, **extra})

    def log_success(self, message: str, **extra):
        """Mock log_success - stores call for assertion."""
        self.success_logs.append({"message": message, **extra})

    def log_error(self, message: str, exc_info: bool = True, **extra):
        """Mock log_error - stores call for assertion."""
        self.error_logs.append({"message": message, "exc_info": exc_info, **extra})

    def log_warning(self, message: str, **extra):
        """Mock log_warning - stores call for assertion."""
        self.warning_logs.append({"message": message, **extra})

    def log_debug(self, message: str, **extra):
        """Mock log_debug - stores call for assertion."""
        self.debug_logs.append({"message": message, **extra})

    def log_progress(self, **metrics):
        """Mock log_progress - stores metrics."""
        self._metrics.update(metrics)

    def success_result(self, **data) -> Dict[str, Any]:
        """Create success result - same as TaskContext."""
        return {
            "status": "success",
            "task_id": self.task_id,
            **data
        }

    def error_result(self, error: str, **data) -> Dict[str, Any]:
        """Create error result - same as TaskContext."""
        return {
            "status": "error",
            "task_id": self.task_id,
            "error": error,
            **data
        }

    def validate_uuid(self, value: str, field_name: str = "id") -> UUID:
        """Validate UUID - same as TaskContext."""
        from .exceptions import TaskValidationError
        try:
            return UUID(value)
        except (ValueError, TypeError, AttributeError) as e:
            raise TaskValidationError(
                f"Invalid UUID format for {field_name}: {value}",
                field=field_name,
                value=value
            ) from e

    def not_found_error(self, message: str, **context):
        """Raise not found error - same as TaskContext."""
        from .exceptions import TaskNotFoundError
        raise TaskNotFoundError(message, **context)

    def validation_error(self, message: str, **context):
        """Raise validation error - same as TaskContext."""
        from .exceptions import TaskValidationError
        raise TaskValidationError(message, **context)

    def config_error(self, message: str, **context):
        """Raise config error - same as TaskContext."""
        from .exceptions import TaskConfigurationError
        raise TaskConfigurationError(message, **context)

    def start_timer(self, name: str):
        """Mock start_timer."""
        import time
        self._timers[name] = time.time()

    def end_timer(self, name: str) -> Optional[float]:
        """Mock end_timer."""
        if name in self._timers:
            import time
            duration = time.time() - self._timers[name]
            return duration
        return None

    def increment_metric(self, name: str, value: int = 1):
        """Mock increment_metric."""
        self._metrics[name] = self._metrics.get(name, 0) + value

    def create_stats_counter(self) -> StatsCounter:
        """Create stats counter - same as TaskContext."""
        return StatsCounter()

    async def commit_batch(self):
        """Mock commit_batch."""
        if self.session and hasattr(self.session, 'commit'):
            await self.session.commit()

    # Assertion helpers

    def assert_logged_info(self, message: Optional[str] = None):
        """Assert that info was logged."""
        assert len(self.info_logs) > 0, "No info logs found"
        if message:
            assert any(message in log["message"] for log in self.info_logs), \
                f"Message '{message}' not found in info logs"

    def assert_logged_success(self, message: Optional[str] = None):
        """Assert that success was logged."""
        assert len(self.success_logs) > 0, "No success logs found"
        if message:
            assert any(message in log["message"] for log in self.success_logs), \
                f"Message '{message}' not found in success logs"

    def assert_logged_error(self, message: Optional[str] = None):
        """Assert that error was logged."""
        assert len(self.error_logs) > 0, "No error logs found"
        if message:
            assert any(message in log["message"] for log in self.error_logs), \
                f"Message '{message}' not found in error logs"

    def assert_logged_warning(self, message: Optional[str] = None):
        """Assert that warning was logged."""
        assert len(self.warning_logs) > 0, "No warning logs found"
        if message:
            assert any(message in log["message"] for log in self.warning_logs), \
                f"Message '{message}' not found in warning logs"


def mock_task_session():
    """
    Create a mock AsyncSession for testing.

    Returns:
        AsyncMock configured as an async database session

    Example:
        session = mock_task_session()
        ctx = TaskTestContext(session=session)
        await my_task(ctx, user_id=123)
        session.commit.assert_called_once()
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


async def run_task_sync(task_func, ctx: TaskTestContext, *args, **kwargs):
    """
    Run an async task function synchronously for testing.

    Args:
        task_func: The async task function to run
        ctx: TaskTestContext instance
        *args: Task arguments
        **kwargs: Task keyword arguments

    Returns:
        Task result

    Example:
        ctx = TaskTestContext()
        result = await run_task_sync(my_async_task, ctx, param1="value")
        assert result["status"] == "success"
    """
    return await task_func(ctx, *args, **kwargs)


# Export public API
__all__ = [
    "TaskTestContext",
    "mock_task_session",
    "run_task_sync",
]
