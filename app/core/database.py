"""
Database configuration and session management.

Provides:
- Async SQLAlchemy engine configuration
- Session factory and dependency
- Database connection verification
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .logging import get_logger
from .models import Base
from .settings import settings

logger = get_logger(__name__)


def get_database_url() -> str:
    """
    Build DATABASE_URL from settings.

    Returns:
        str: PostgreSQL connection URL with asyncpg driver
    """
    return settings.database_url


DATABASE_URL = get_database_url()

# Create async engine with connection pooling
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

# Create async session factory
async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide an async database session.

    Inject it via the ``SessionDep`` alias declared at the bottom of this
    module — never an inline ``Depends()`` default (PROJECT_CONVENTIONS §5).

    Usage — the route hands the session to its service, and the service commits
    (CRUD only flushes; CLAUDE.md §2):
        @router.post("/users")
        async def create_user(
            data: UserCreate, session: SessionDep, service: UserServiceDep
        ) -> UserResponse:
            return await service.create_user(session, data)

    This dependency never commits. On an unexpected error it rolls back; a named
    ``HTTPException`` passes through, and closing the session discards anything
    left uncommitted.

    Exit scope: this dependency uses the default ``scope="request"``, so the
    session stays open until after the response is sent — which is what lets
    lazy-loaded ORM attributes resolve during response serialization.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise


async def verify_db_connection(max_retries: int = 5, retry_delay: float = 2.0) -> None:
    """Verify database connectivity at startup with retry logic."""
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"Database connected. PostgreSQL: {version}")
                return
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"DB connection attempt {attempt}/{max_retries} failed. Retrying...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts")

    raise last_exception if last_exception else Exception("Database connection failed")


async def shutdown_db() -> None:
    """Gracefully shutdown the database engine."""
    await engine.dispose()
    logger.info("Database engine disposed")


SessionDep = Annotated[AsyncSession, Depends(get_session)]

__all__ = [
    "Base",
    "get_session",
    "SessionDep",
    "verify_db_connection",
    "shutdown_db",
    "engine",
    "get_database_url",
    "async_session_factory",
]
