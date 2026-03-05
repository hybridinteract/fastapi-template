"""
Background Task Framework - Core Library

This module contains the internal implementation of the background task framework.
Most users should import from app.core.background instead of this module directly.
"""

# Core decorators
from .decorators import (
    simple_task,
    db_task,
)

# Task context
from .context import TaskContext

# Base task classes
from .base import (
    BaseTask,
    DatabaseTask,
)

# Exceptions
from .exceptions import (
    TaskException,
    TaskValidationError,
    TaskNotFoundError,
    TaskConfigurationError,
    TaskTimeoutError,
    NON_RETRIABLE_EXCEPTIONS,
    is_retriable_error,
)

# Retry policies
from .retry import (
    RETRY_POLICIES,
    get_retry_policy,
)

# Session management
from .session import (
    get_task_session,
    TaskSessionManager,
)

# Event loop utilities
from .event_loop import (
    run_with_event_loop,
    get_or_create_event_loop,
)

# Logging
from .logging import TaskLogger

# Monitoring
from .monitoring import (
    TaskMetrics,
    Timer,
    StatsCounter,
    log_metric,
)

# Testing utilities
from .testing import (
    TaskTestContext,
    mock_task_session,
    run_task_sync,
)


__all__ = [
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
    "NON_RETRIABLE_EXCEPTIONS",
    "is_retriable_error",

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
