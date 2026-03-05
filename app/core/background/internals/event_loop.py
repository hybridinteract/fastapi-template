"""
Event Loop Management for Background Tasks

This module provides utilities to safely run async functions in Celery tasks.

The key insight: Celery worker processes create a single event loop during
worker_process_init (see app/core/background/celery_app.py). Reusing this loop
with proper connection pooling (AsyncAdaptedQueuePool) provides optimal performance
for async database operations.

Design:
- One event loop per worker process (created in worker_process_init)
- All tasks in the worker reuse this loop
- AsyncAdaptedQueuePool provides connection pooling (3-8 connections per worker)
- Worker process restarts after max_tasks_per_child to prevent memory leaks

IMPORTANT: Never create a new event loop in a task unless absolutely necessary.
Reusing the worker's event loop ensures all async database connections work
correctly across multiple task executions.
"""

import asyncio
from typing import Any, Callable, Coroutine, TypeVar, Union
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


def run_with_event_loop(
    async_func: Union[Callable[..., Coroutine[Any, Any, T]], Coroutine[Any, Any, T]],
    *args,
    **kwargs
) -> T:
    """
    Safely run async function in Celery task.

    This function reuses the worker's event loop (created in worker_process_init)
    instead of creating a new one, preventing "attached to different loop" errors
    with async database drivers like asyncpg.

    Args:
        async_func: Either an async function (callable) or coroutine object
        *args: Arguments to pass to async_func (if it's callable)
        **kwargs: Keyword arguments to pass to async_func (if it's callable)

    Returns:
        Result of the async function

    Raises:
        Any exception raised by the async function

    Example:
        # With callable async function
        result = run_with_event_loop(my_async_function, arg1, arg2, kwarg=value)

        # With coroutine object
        coro = my_async_function(arg1, arg2)
        result = run_with_event_loop(coro)

    Technical Notes:
        - Reuses worker's event loop (one per worker process)
        - Falls back to creating new loop only if none exists (shouldn't happen)
        - Does NOT close the loop after execution (shared across all tasks in worker)
        - Works with AsyncAdaptedQueuePool (proper connection pooling)
        - Event loop is disposed when worker process exits via max_tasks_per_child
        - Async generator cleanup happens at worker shutdown, not per-task
    """
    loop = _get_event_loop()

    try:
        # If it's a callable, call it with arguments to get the coroutine
        if callable(async_func):
            coro = async_func(*args, **kwargs)
        else:
            # It's already a coroutine object
            coro = async_func

        # Run the coroutine to completion
        # Note: We do NOT call shutdown_asyncgens() here - that should only
        # happen at worker shutdown, not after each task. Calling it per-task
        # can cause issues with connection pools and async generators.
        return loop.run_until_complete(coro)

    except Exception as e:
        logger.error(
            f"Error running async task: {e}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        raise


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get the current event loop in a Python 3.10+ compatible way.

    This handles the deprecation of asyncio.get_event_loop() which will
    raise DeprecationWarning in Python 3.10+ when called outside an
    async context.

    Returns:
        The current or newly created event loop
    """
    try:
        # First, try to get a running loop (only works inside async context)
        return asyncio.get_running_loop()
    except RuntimeError:
        # Not in async context, try to get the current thread's event loop
        pass

    # For worker processes, there should be an event loop set up in
    # worker_process_init. Try to get it without triggering deprecation.
    try:
        # This is the Python 3.10+ safe way to get an existing loop
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            logger.warning(
                "Event loop is closed, creating new one. "
                "This indicates a problem with worker lifecycle management."
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            logger.debug(f"Reusing worker event loop: {id(loop)}")
        return loop
    except RuntimeError as e:
        # No event loop exists, create one
        logger.warning(
            f"No event loop found ({e}), creating new one. "
            "This is unexpected in a Celery worker and may indicate a configuration issue."
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug(f"Created new event loop: {id(loop)}")
        return loop


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get the current event loop or create a new one if none exists.

    This is useful for tasks that need direct access to the event loop
    for advanced async operations (e.g., creating tasks, managing futures).

    Returns:
        The current or newly created event loop

    Example:
        loop = get_or_create_event_loop()
        task = loop.create_task(my_coroutine())
        loop.run_until_complete(task)

    Note:
        Prefer run_with_event_loop() for simple async function execution.
        Only use this if you need direct loop access for advanced use cases.
    """
    return _get_event_loop()


# Export public API
__all__ = [
    "run_with_event_loop",
    "get_or_create_event_loop",
]
