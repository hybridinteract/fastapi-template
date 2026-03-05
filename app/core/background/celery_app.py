"""
Celery Application Configuration

This module configures the Celery application for background task processing.
It follows the application factory pattern and integrates with FastAPI settings.

Task Discovery:
    Tasks are auto-discovered from tasks.py files in each app module:
    - app/user/tasks.py
    - app/product/tasks.py (future)
    - app/order/tasks.py (future)

    Each module should define tasks using @celery_app.task decorator.
"""

import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, worker_process_init
from celery.schedules import crontab
from kombu import Exchange, Queue
from app.core.settings import settings
from app.core.logging import get_logger

# Configure logging
logger = get_logger(__name__)


def get_installed_apps() -> list:
    """
    Discover all app modules that have tasks.py files.

    Scans the app directory for modules containing tasks.py and returns
    a list of module paths for Celery autodiscovery.

    Returns:
        list: List of app module paths (e.g., ['app.user', 'app.product'])
    """
    # Go up from app/core/background/celery_app.py to app/
    # __file__ = app/core/background/celery_app.py
    # dirname(__file__) = app/core/background
    # dirname(dirname(__file__)) = app/core
    # dirname(dirname(dirname(__file__))) = app
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    apps = []

    # Directories to exclude from task discovery
    exclude_dirs = {'core', 'background', '__pycache__'}

    # Scan for directories in app/ that have tasks.py
    for item in os.listdir(app_dir):
        # Skip excluded directories and private modules
        if item.startswith('_') or item in exclude_dirs:
            continue

        item_path = os.path.join(app_dir, item)
        if os.path.isdir(item_path):
            # Check if tasks.py exists in this module
            tasks_file = os.path.join(item_path, 'tasks.py')
            if os.path.exists(tasks_file):
                apps.append(f"app.{item}")
                logger.debug(f"Found tasks in: app.{item}")

    return apps


def create_celery_app() -> Celery:
    """
    Create and configure Celery application.

    Returns:
        Celery: Configured Celery application instance
    """
    celery_app = Celery(
        settings.APP_NAME,
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )

    # Configure Celery with settings
    celery_app.conf.update(
        # Task serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,

        # Task tracking and execution
        task_track_started=settings.CELERY_TASK_TRACK_STARTED,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_acks_late=settings.CELERY_TASK_ACKS_LATE,
        task_reject_on_worker_lost=settings.CELERY_TASK_REJECT_ON_WORKER_LOST,

        # Task compression for large payloads
        task_compression=settings.CELERY_TASK_COMPRESSION if settings.CELERY_TASK_COMPRESSION else None,
        result_compression=settings.CELERY_TASK_COMPRESSION if settings.CELERY_TASK_COMPRESSION else None,

        # Worker settings
        worker_pool=settings.CELERY_WORKER_POOL,
        worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
        worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
        worker_lost_wait=settings.CELERY_WORKER_LOST_WAIT,
        worker_send_task_events=True,
        worker_disable_rate_limits=False,

        # Broker settings
        broker_connection_retry_on_startup=settings.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP,
        broker_connection_retry=True,
        broker_connection_max_retries=settings.CELERY_BROKER_CONNECTION_MAX_RETRIES,
        broker_pool_limit=10,

        # Result backend settings
        result_expires=settings.CELERY_RESULT_EXPIRES,
        result_extended=True,
        result_backend_thread_safe=settings.CELERY_RESULT_BACKEND_THREAD_SAFE,

        # Task result settings
        task_send_sent_event=True,
        task_ignore_result=False,

        # Queue configuration
        task_default_queue="default",
        task_default_exchange="default",
        task_default_routing_key="default",

        # Define task queues
        task_queues=(
            Queue("default", Exchange("default"), routing_key="default"),
            Queue("high_priority", Exchange("high_priority"),
                  routing_key="high_priority"),
            Queue("low_priority", Exchange("low_priority"),
                  routing_key="low_priority"),
        ),

        # Beat schedule for periodic tasks
        beat_schedule={
            # Task result cleanup - prevents Redis memory growth
            "cleanup-expired-results-daily": {
                "task": "app.core.background.tasks.cleanup_expired_task_results",
                "schedule": crontab(hour=3, minute=0),  # Run daily at 3 AM
                "args": (2,),  # Clean results older than 2 days
            },
            # Example: Add more scheduled tasks here
            # "send-daily-report": {
            #     "task": "app.reports.tasks.send_daily_report",
            #     "schedule": crontab(hour=9, minute=0),  # 9 AM daily
            # },
        },
    )

    # Auto-discover tasks from all app modules that have tasks.py
    installed_apps = get_installed_apps()

    # Also include core background tasks
    installed_apps.append("app.core.background")

    if installed_apps:
        logger.info(
            f"Auto-discovering tasks from: {', '.join(installed_apps)}")
        celery_app.autodiscover_tasks(installed_apps)
    else:
        logger.warning("No app modules with tasks.py found")

    return celery_app


# Create Celery application instance
celery_app = create_celery_app()


def discover_and_import_models() -> list:
    """
    Auto-discover and import all SQLAlchemy models.

    This ensures all models are properly registered with SQLAlchemy before
    database operations in worker processes. Import order matters - models
    must be imported in dependency order.

    Returns:
        list: List of imported model module paths

    Raises:
        Exception: If model imports fail
    """
    import importlib
    from pathlib import Path

    # Ordered imports to respect dependencies
    # Add your models here in dependency order (base models first)
    ordered_modules = [
        "app.core.models",              # Base
        # "app.user.models",            # User (referenced by many)
        # Add more models as you create modules
    ]

    imported = []

    for module_path in ordered_modules:
        try:
            module = importlib.import_module(module_path)
            imported.append(module_path)
            logger.debug(f"Imported models from: {module_path}")
        except ImportError as e:
            logger.warning(f"Could not import {module_path}: {e}")
        except Exception as e:
            logger.error(f"Error importing {module_path}: {e}", exc_info=True)
            raise

    # Auto-discover any additional models not in the ordered list
    app_dir = Path(__file__).parent.parent.parent  # Go up to /app
    for item in app_dir.iterdir():
        if item.is_dir() and not item.name.startswith('_'):
            models_file = item / "models.py"
            if models_file.exists():
                module_path = f"app.{item.name}.models"
                if module_path not in imported:
                    try:
                        module = importlib.import_module(module_path)
                        imported.append(module_path)
                        logger.debug(f"Auto-discovered models: {module_path}")
                    except ImportError as e:
                        logger.warning(f"Could not import {module_path}: {e}")
                    except Exception as e:
                        logger.error(
                            f"Error importing {module_path}: {e}", exc_info=True)

    logger.info(
        f"Imported {len(imported)} model modules: {', '.join(imported)}")
    return imported


# ==================== Celery Signals ====================

@worker_ready.connect
def on_worker_ready(sender=None, conf=None, **kwargs):
    """Signal handler called when Celery worker is ready."""
    logger.info("=" * 60)
    logger.info("Celery Worker Started Successfully")
    logger.info(f"Broker: {settings.celery_broker_url}")
    logger.info(f"Backend: {settings.celery_result_backend}")
    logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")
    logger.info("=" * 60)


@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs):
    """Signal handler called when Celery worker is shutting down."""
    logger.info("=" * 60)
    logger.info("Celery Worker Shutting Down...")
    logger.info("=" * 60)


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Reinitialize database engine after worker process fork.

    This is critical for async drivers like asyncpg which are not fork-safe.
    When using prefork worker pool, the parent process creates the database
    engine, but after fork(), the child processes need their own engine
    with fresh connections and event loops.

    This also ensures all SQLAlchemy models are properly imported and
    configured in the worker process.

    This signal is called after each worker process is forked from the parent.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core import database

    worker_pid = kwargs.get('pid', os.getpid())
    logger.info(
        f"Initializing database engine for worker process {worker_pid}")

    try:
        # CRITICAL: Import all models BEFORE engine initialization
        # This ensures SQLAlchemy mapper configuration works correctly
        # Import order matters - base models first, then dependent models
        try:
            discover_and_import_models()
            logger.debug(
                f"All models imported successfully in worker {worker_pid}")
        except Exception as e:
            logger.error(
                f"Failed to import models in worker {worker_pid}: {e}", exc_info=True)
            raise

        # Dispose of the engine from the parent process
        # This needs to be done synchronously in the forked process
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(database.engine.dispose())
            # Keep the loop open - it will be reused by tasks
            logger.debug(f"Event loop created and set for worker {worker_pid}")
        except Exception as e:
            logger.warning(f"Could not dispose parent engine: {e}")

        # Create new engine for this worker process
        # Use proper connection pooling with Celery-specific settings
        # The single event loop per worker (created above) works correctly with
        # AsyncAdaptedQueuePool since all async operations in this worker process
        # will use the same loop.
        from sqlalchemy.pool import AsyncAdaptedQueuePool

        new_engine = create_async_engine(
            database.get_database_url(),
            echo=settings.DB_ECHO,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=settings.CELERY_DB_POOL_SIZE,
            max_overflow=settings.CELERY_DB_MAX_OVERFLOW,
            pool_recycle=settings.CELERY_DB_POOL_RECYCLE,
            pool_pre_ping=True,
            pool_timeout=30,
        )

        # Create new session factory
        new_session_factory = sessionmaker(
            new_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Replace the global engine and session factory
        database.engine = new_engine
        database.async_session_factory = new_session_factory

        logger.info(
            f"Database engine successfully reinitialized for worker {worker_pid}"
        )

    except Exception as e:
        logger.error(
            f"Failed to reinitialize database engine for worker {worker_pid}: {e}",
            exc_info=True
        )
        raise


# ==================== Helper Functions ====================

def get_task_info(task_id: str) -> dict:
    """
    Get information about a specific task.

    Args:
        task_id: The task ID to query

    Returns:
        dict: Task information including state, result, and metadata
    """
    from celery.result import AsyncResult

    task_result = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "state": task_result.state,
        "result": task_result.result if task_result.ready() else None,
        "info": task_result.info,
        "successful": task_result.successful() if task_result.ready() else None,
        "failed": task_result.failed() if task_result.ready() else None,
    }


def revoke_task(task_id: str, terminate: bool = False, signal: str = "SIGTERM") -> dict:
    """
    Revoke/cancel a running task.

    Args:
        task_id: The task ID to revoke
        terminate: If True, terminate the task immediately
        signal: Signal to send when terminating (default: SIGTERM)

    Returns:
        dict: Status of the revocation
    """
    celery_app.control.revoke(task_id, terminate=terminate, signal=signal)

    return {
        "task_id": task_id,
        "revoked": True,
        "terminated": terminate,
    }


# Export for convenience
__all__ = ["celery_app", "create_celery_app", "get_task_info", "revoke_task"]
