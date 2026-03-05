"""
Database Session Management for Background Tasks

This module provides session management utilities specifically designed
for Celery background tasks.

Key differences from FastAPI's get_session():
- Works with NullPool (no connection pooling for workers)
- Reuses worker's event loop (prevents "attached to different loop" errors)
- Skips rollback for validation errors (no DB changes made)
- Designed for background task context, not HTTP request context

The TaskSessionManager ensures:
1. Fresh database connections for each task
2. Proper cleanup even on exceptions
3. Compatibility with async database drivers (asyncpg)
4. No connection pool issues with forked worker processes
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_factory
from app.core.logging import get_logger
from .exceptions import TaskValidationError, TaskNotFoundError, TaskConfigurationError

logger = get_logger(__name__)


@asynccontextmanager
async def get_task_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions in Celery tasks.

    This provides a fresh database session for each task execution,
    with automatic rollback on errors and cleanup on completion.

    Yields:
        AsyncSession: Database session for the task

    Example:
        async with get_task_session() as session:
            user = await user_crud.get(session, user_id)
            await session.commit()

    Technical Notes:
        - Uses async_session_factory (configured with NullPool in workers)
        - Reuses worker's event loop (from worker_process_init)
        - Skips rollback for validation errors (no DB modifications)
        - Always closes session properly via context manager

    Error Handling:
        - TaskValidationError: No rollback (no DB changes)
        - TaskNotFoundError: No rollback (no DB changes)
        - TaskConfigurationError: No rollback (no DB changes)
        - Other exceptions: Automatic rollback before re-raising
    """
    async with async_session_factory() as session:
        try:
            yield session
        except (TaskValidationError, TaskNotFoundError, TaskConfigurationError):
            # Don't rollback for validation errors - no DB changes were made
            # Just re-raise the exception to let the task fail with proper error type
            raise
        except Exception as e:
            # For all other exceptions, rollback any uncommitted changes
            logger.error(
                f"Task session error, rolling back: {e}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            await session.rollback()
            raise
        # Note: session.close() is handled by the async_session_factory context manager


class TaskSessionManager:
    """
    Reusable session manager for background tasks.

    This class can be used directly in tasks that need more control
    over session lifecycle, or as a base for custom session managers.

    Example:
        session_manager = TaskSessionManager()
        async with session_manager() as session:
            # Use session
            pass
    """

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provide async context manager interface.

        This allows TaskSessionManager instances to be used with async with.

        Yields:
            AsyncSession: Database session
        """
        async with get_task_session() as session:
            yield session


# Export public API
__all__ = [
    "get_task_session",
    "TaskSessionManager",
]
