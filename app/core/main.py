"""
FastAPI Application Entry Point.

This module initializes and configures the FastAPI application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .settings import settings
from .database import verify_db_connection, shutdown_db
from .exceptions import register_exception_handlers
from .middleware import setup_middleware
from .logging import setup_logging, get_logger
from .metrics import instrumentator
from ..apis.v1 import router as api_v1_router
from ..user.seed import run_seed

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Verify database connection
    await verify_db_connection()

    # Run database seed (idempotent - only creates missing data)
    try:
        await run_seed(dispose_engine=False)
    except Exception as e:
        logger.error(f"Database seed failed: {e}")
        # Continue startup even if seed fails

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await shutdown_db()
    logger.info("Application shutdown complete")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=f"{settings.APP_NAME} API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Setup all middleware (CORS, GZip, TrustedHost, Request Timing)
    setup_middleware(app)

    # Register exception handlers
    register_exception_handlers(app)

    # Include API routers
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # Prometheus metrics - exposes /metrics endpoint
    instrumentator.instrument(app).expose(app, include_in_schema=False)

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": settings.APP_NAME}

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
        }

    return app


# Create the application instance
app = create_application()
