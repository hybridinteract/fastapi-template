"""
Exception handlers configuration for the FastAPI application.

This module contains all exception handlers including validation errors,
database errors, HTTP exceptions, and global error handling.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError
from datetime import datetime

from .logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Configure all application exception handlers.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors with detailed messages."""
        logger.warning(
            f"Validation error on {request.url.path}: {exc.errors()}")

        # Convert errors to JSON serializable format
        serializable_errors = []
        for error in exc.errors():
            serializable_error = {}
            for key, value in error.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    serializable_error[key] = value
                elif isinstance(value, (list, tuple)):
                    serializable_error[key] = list(value)
                else:
                    serializable_error[key] = str(value)
            serializable_errors.append(serializable_error)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "detail": serializable_errors,
                "body": str(exc.body) if exc.body else None,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation errors."""
        logger.warning(
            f"Pydantic validation error on {request.url.path}: {exc.errors()}")
        
        # Convert errors to JSON serializable format
        serializable_errors = []
        for error in exc.errors():
            serializable_error = {}
            for key, value in error.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    serializable_error[key] = value
                elif isinstance(value, (list, tuple)):
                    serializable_error[key] = list(value)
                else:
                    serializable_error[key] = str(value)
            serializable_errors.append(serializable_error)
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Data Validation Error",
                "detail": serializable_errors,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        """Handle database integrity constraint violations."""
        logger.error(
            f"Database integrity error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "Data Integrity Error",
                "detail": "The operation violates a database constraint. This might be due to duplicate data or invalid references.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(OperationalError)
    async def operational_exception_handler(request: Request, exc: OperationalError):
        """Handle database operational errors (connection issues, etc.)."""
        logger.error(
            f"Database operational error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Service Unavailable",
                "detail": "Database service is temporarily unavailable. Please try again later.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """Handle general database errors gracefully."""
        logger.error(f"Database error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Database Error",
                "detail": "A database error occurred. Please try again later.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(ValueError)
    async def value_exception_handler(request: Request, exc: ValueError):
        """Handle value errors (invalid input data)."""
        logger.warning(f"Value error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid Input",
                "detail": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(PermissionError)
    async def permission_exception_handler(request: Request, exc: PermissionError):
        """Handle permission errors."""
        logger.warning(f"Permission error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Permission Denied",
                "detail": "You don't have permission to perform this action.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_exception_handler(request: Request, exc: FileNotFoundError):
        """Handle file not found errors."""
        logger.error(f"File not found error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "File Not Found",
                "detail": "The requested file or resource could not be found.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(TimeoutError)
    async def timeout_exception_handler(request: Request, exc: TimeoutError):
        """Handle timeout errors."""
        logger.error(f"Timeout error on {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            content={
                "error": "Request Timeout",
                "detail": "The request took too long to process. Please try again.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler for unhandled exceptions."""
        logger.error(
            f"Unhandled exception on {request.url.path}: {str(exc)}",
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": "An unexpected error occurred. Please try again later.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            },
        )

    logger.info("✓ All exception handlers configured successfully")
