"""
Middleware configuration for the FastAPI application.

This module contains all middleware setup including CORS, compression,
security headers, and custom request processing middleware.
"""
from starlette.types import ASGIApp, Receive, Scope, Send
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .settings import settings
from .logging import get_logger
import time


class GZipMiddlewareExcludeStreaming:
    """GZip middleware that skips SSE / streaming endpoints.

    GZip buffers the entire response before compressing, which kills
    Server-Sent Events streaming.  This wrapper checks the request path
    and bypasses GZip for paths containing '/stream'.
    """

    def __init__(self, app: ASGIApp, minimum_size: int = 500) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and "/stream" in scope.get("path", ""):
            await self.app(scope, receive, send)
        else:
            await self.gzip(scope, receive, send)

logger = get_logger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all application middleware.

    Note: Middleware is executed in reverse order of addition.

    Args:
        app: FastAPI application instance
    """

    # 1. Trusted Host Middleware (Security) - Only in production
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.TRUSTED_HOSTS
        )
        logger.info(
            f"✓ Trusted Host Middleware enabled: {settings.TRUSTED_HOSTS}")

    # 2. CORS Middleware - Allow cross-origin requests
    cors_kwargs = {
        "allow_origins": settings.cors_origins_list,
        "allow_credentials": settings.CORS_ALLOW_CREDENTIALS,
        "allow_methods": settings.CORS_ALLOW_METHODS,
        "allow_headers": settings.CORS_ALLOW_HEADERS,
    }

    # Add regex pattern if configured
    if settings.CORS_ORIGIN_REGEX:
        cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX
        logger.info(f"✓ CORS Middleware enabled with regex: {settings.CORS_ORIGIN_REGEX}")

    app.add_middleware(CORSMiddleware, **cors_kwargs)
    logger.info(f"✓ CORS Middleware enabled: {settings.cors_origins_list}")

    # 3. GZip Middleware - Response compression (skips SSE/streaming endpoints)
    if settings.ENABLE_GZIP:
        app.add_middleware(
            GZipMiddlewareExcludeStreaming,
            minimum_size=settings.GZIP_MINIMUM_SIZE
        )
        logger.info(
            f"✓ GZip Middleware enabled (min size: {settings.GZIP_MINIMUM_SIZE} bytes, "
            f"streaming endpoints excluded)")

    # 4. Custom Request Timing Middleware
    @app.middleware("http")
    async def process_time_middleware(request: Request, call_next):
        """
        Add X-Process-Time header to track request processing time.
        Also logs slow requests for monitoring.
        """
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # Add processing time to response headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # Log slow requests (> 1 second)
        if process_time > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.4f}s"
            )

        return response

    logger.info("✓ All middleware configured successfully")
