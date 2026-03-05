"""
Logging configuration for the FastAPI application.

This module contains all logging setup including formatters, handlers,
and logger configuration for different environments.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any

from .settings import settings

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def get_log_format(include_colors: bool = False) -> str:
    """
    Get the appropriate log format string.
    
    Args:
        include_colors: Whether to include color codes for console output
        
    Returns:
        str: Log format string
    """
    if include_colors and settings.DEBUG:
        # Colored format for development
        return (
            "\033[90m%(asctime)s\033[0m - "
            "\033[36m%(name)s\033[0m - "
            "%(levelname_color)s%(levelname)s\033[0m - "
            "%(message)s"
        )
    else:
        # Standard format for production and file logging
        return "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""
    
    COLORS = {
        'DEBUG': '\033[94m',    # Blue
        'INFO': '\033[92m',     # Green
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',    # Red
        'CRITICAL': '\033[95m', # Magenta
    }
    
    def format(self, record):
        # Add color to the record
        record.levelname_color = self.COLORS.get(record.levelname, '')
        return super().format(record)


def setup_console_handler() -> logging.Handler:
    """
    Setup console handler with appropriate formatting.
    
    Returns:
        logging.Handler: Configured console handler
    """
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.DEBUG:
        # Use colored formatter for development
        formatter = ColoredFormatter(get_log_format(include_colors=True))
    else:
        # Use standard formatter for production
        formatter = logging.Formatter(get_log_format(include_colors=False))
    
    console_handler.setFormatter(formatter)
    return console_handler


def setup_file_handler() -> logging.Handler:
    """
    Setup rotating file handler for persistent logging.
    
    Returns:
        logging.Handler: Configured file handler
    """
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=LOGS_DIR / f"{settings.APP_NAME.lower().replace(' ', '_')}.log",
            maxBytes=settings.LOG_FILE_MAX_SIZE,
            backupCount=settings.LOG_FILE_BACKUP_COUNT,
            encoding='utf-8'
        )
    except PermissionError:
        # Fallback to console-only logging if file permissions fail
        print(f"Warning: Cannot write to {LOGS_DIR}. File logging disabled.")
        return None
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(formatter)
    return file_handler


def setup_error_file_handler() -> logging.Handler:
    """
    Setup separate file handler for error logs.
    
    Returns:
        logging.Handler: Configured error file handler
    """
    try:
        error_handler = logging.handlers.RotatingFileHandler(
            filename=LOGS_DIR / f"{settings.APP_NAME.lower().replace(' ', '_')}_errors.log",
            maxBytes=settings.LOG_FILE_MAX_SIZE,
            backupCount=settings.LOG_FILE_BACKUP_COUNT,
            encoding='utf-8'
        )
    except PermissionError:
        print(f"Warning: Cannot write error logs to {LOGS_DIR}. Error file logging disabled.")
        return None
    
    error_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    error_handler.setFormatter(formatter)
    return error_handler


def configure_third_party_loggers() -> None:
    """Configure logging levels for third-party libraries."""
    
    # SQLAlchemy logging
    if settings.DEBUG:
        # Show SQL queries in debug mode
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    else:
        # Reduce SQLAlchemy noise in production
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    
    # FastAPI/Uvicorn logging
    logging.getLogger('uvicorn.access').setLevel(logging.INFO)
    logging.getLogger('uvicorn.error').setLevel(logging.INFO)
    
    # HTTP libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Other common libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def setup_logging() -> logging.Logger:
    """
    Configure application logging with handlers and formatters.
    
    Returns:
        logging.Logger: Configured root logger
    """
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Set the root logging level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Setup handlers
    handlers = []
    
    # Console handler (always enabled)
    console_handler = setup_console_handler()
    handlers.append(console_handler)
    
    # File handlers (enabled based on settings)
    if settings.ENABLE_FILE_LOGGING:
        file_handler = setup_file_handler()
        if file_handler:
            handlers.append(file_handler)
        
        # Separate error log file
        error_handler = setup_error_file_handler()
        if error_handler:
            handlers.append(error_handler)
    
    # Add all handlers to root logger
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Configure third-party loggers
    configure_third_party_loggers()
    
    # Get application logger
    app_logger = logging.getLogger(__name__)
    
    # Log configuration summary
    app_logger.info("=" * 60)
    app_logger.info("Logging Configuration Summary")
    app_logger.info(f"Log Level: {settings.LOG_LEVEL}")
    app_logger.info(f"Environment: {settings.ENVIRONMENT}")
    app_logger.info(f"Debug Mode: {settings.DEBUG}")
    app_logger.info(f"Handlers: {len(handlers)} configured")
    
    if settings.ENABLE_FILE_LOGGING:
        app_logger.info(f"Log Directory: {LOGS_DIR.absolute()}")
        app_logger.info(f"Max File Size: {settings.LOG_FILE_MAX_SIZE // (1024*1024)}MB")
        app_logger.info(f"Backup Count: {settings.LOG_FILE_BACKUP_COUNT}")
    
    app_logger.info("=" * 60)
    
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)
