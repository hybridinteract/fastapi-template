"""
Database configuration and session management.

Provides:
- Async SQLAlchemy engine configuration
- Session factory and dependency
- Database connection verification
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import AsyncGenerator
import asyncio
from fastapi import HTTPException

from .models import Base
from .settings import settings
from .logging import get_logger

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
async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide an async database session.
    
    Usage:
        @router.post("/user")
        async def create_user(session: AsyncSession = Depends(get_session)):
            user = await user_crud.create(session, data)
            await session.commit()
            return user
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


__all__ = ["Base", "get_session", "verify_db_connection", "shutdown_db", "engine", "get_database_url", "async_session_factory"]
