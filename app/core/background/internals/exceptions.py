"""
Background Task Exceptions

This module defines exceptions specific to Celery background tasks,
with clear distinction between retriable and non-retriable errors.

The `retriable` attribute helps the framework decide whether to retry
a failed task or mark it as permanently failed.
"""


class TaskException(Exception):
    """
    Base exception for all background task errors.

    By default, task exceptions are retriable, meaning Celery will
    attempt to retry the task according to the configured retry policy.

    Attributes:
        retriable (bool): Whether this exception should trigger a task retry.
            Default: True
    """

    retriable = True

    def __init__(self, message: str, **context):
        """
        Initialize task exception.

        Args:
            message: Error message describing what went wrong
            **context: Additional context information (entity_id, operation, etc.)
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self):
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class TaskValidationError(TaskException):
    """
    Validation error in task input parameters.

    This error indicates that the task was called with invalid arguments
    (e.g., malformed UUID, missing required fields, invalid data format).

    These errors are NOT retriable because retrying with the same invalid
    input will always fail. The caller should fix the input and retry manually.

    Examples:
        - Invalid UUID format
        - Missing required parameter
        - Invalid email format
        - Out-of-range value
    """

    retriable = False


class TaskNotFoundError(TaskException):
    """
    Resource not found error.

    This error indicates that a required database resource (user, booking,
    provider, etc.) was not found.

    These errors are NOT retriable because retrying won't make the missing
    resource appear. The caller should verify the resource exists before
    triggering the task.

    Examples:
        - User ID doesn't exist
        - Booking not found
        - Service provider not found
    """

    retriable = False


class TaskConfigurationError(TaskException):
    """
    Task misconfiguration error.

    This error indicates that the task itself is incorrectly configured
    (e.g., missing required environment variables, invalid settings,
    missing external service credentials).

    These errors are NOT retriable because the task configuration must
    be fixed before the task can succeed.

    Examples:
        - Missing API key for external service
        - Invalid queue configuration
        - Missing required task parameter default
    """

    retriable = False


class TaskTimeoutError(TaskException):
    """
    Task execution timeout error.

    This error indicates that the task exceeded its time limit
    (soft or hard time limit configured in Celery).

    These errors ARE retriable because the task might succeed if
    executed again (e.g., if the database or external service
    responds faster on retry).

    Examples:
        - Database query timeout
        - External API timeout
        - Long-running computation exceeded limit
    """

    retriable = True


# Database-specific error handling
try:
    from sqlalchemy.exc import (
        OperationalError,
        DatabaseError,
        DisconnectionError,
        TimeoutError as SQLAlchemyTimeoutError,
        IntegrityError,
        DataError,
    )

    # Database errors that should trigger retries (transient errors)
    RETRIABLE_DB_EXCEPTIONS = (
        OperationalError,       # Connection lost, database unavailable
        DisconnectionError,     # Pool disconnection
        SQLAlchemyTimeoutError, # Query timeout
    )

    # Database errors that should NOT be retried (permanent errors)
    NON_RETRIABLE_DB_EXCEPTIONS = (
        IntegrityError,  # Constraint violation, duplicate key
        DataError,       # Data type mismatch, invalid data
    )

except ImportError:
    # SQLAlchemy not available (shouldn't happen, but handle gracefully)
    RETRIABLE_DB_EXCEPTIONS = ()
    NON_RETRIABLE_DB_EXCEPTIONS = ()


# Non-retriable exceptions tuple for easy checking
NON_RETRIABLE_EXCEPTIONS = (
    TaskValidationError,
    TaskNotFoundError,
    TaskConfigurationError,
) + NON_RETRIABLE_DB_EXCEPTIONS


def is_retriable_error(exc: Exception) -> bool:
    """
    Check if an exception should trigger a task retry.

    This function examines the exception type and determines whether
    the task should be retried or marked as permanently failed.

    Args:
        exc: Exception raised by the task

    Returns:
        bool: True if the task should be retried, False otherwise

    Examples:
        >>> is_retriable_error(TaskValidationError("Invalid UUID"))
        False

        >>> is_retriable_error(OperationalError("Connection lost"))
        True

        >>> is_retriable_error(IntegrityError("Duplicate key"))
        False

    Logic:
        1. Non-retriable task exceptions → False
        2. Non-retriable database exceptions → False
        3. Retriable database exceptions → True
        4. TaskException with retriable=False → False
        5. TaskException with retriable=True → True
        6. Unknown exceptions → True (safe default, let retry policy handle)
    """
    # Check if it's a non-retriable task exception
    if isinstance(exc, NON_RETRIABLE_EXCEPTIONS):
        return False

    # Check if it's a retriable database exception
    if RETRIABLE_DB_EXCEPTIONS and isinstance(exc, RETRIABLE_DB_EXCEPTIONS):
        return True

    # Check if it's a TaskException with explicit retriable flag
    if isinstance(exc, TaskException):
        return exc.retriable

    # Default: retry on unknown exceptions
    # This is safer - let the retry policy handle limits
    return True


# Export all exceptions
__all__ = [
    "TaskException",
    "TaskValidationError",
    "TaskNotFoundError",
    "TaskConfigurationError",
    "TaskTimeoutError",
    "NON_RETRIABLE_EXCEPTIONS",
    "RETRIABLE_DB_EXCEPTIONS",
    "NON_RETRIABLE_DB_EXCEPTIONS",
    "is_retriable_error",
]
