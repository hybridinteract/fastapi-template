"""
Object Storage module for S3-compatible storage.

Simplified, modern implementation using boto3 for file operations
with generic S3-compatible storage services.
"""

from .exceptions import (
    FileDeleteError,
    FileNotFoundError,
    FileSizeError,
    FileTypeError,
    FileUploadError,
    FileValidationError,
    StorageConnectionError,
    StorageException,
)
from .storage import StorageService, get_storage
from .utils import (
    calculate_hash,
    detect_mime_type,
    generate_key,
    process_image,
    validate_file,
    validate_image,
    verify_hash,
)

__all__ = [
    # Storage service
    "StorageService",
    "get_storage",
    # Utility functions
    "validate_file",
    "validate_image",
    "detect_mime_type",
    "process_image",
    "generate_key",
    "calculate_hash",
    "verify_hash",
    # Exceptions
    "StorageException",
    "StorageConnectionError",
    "FileUploadError",
    "FileValidationError",
    "FileSizeError",
    "FileTypeError",
    "FileNotFoundError",
    "FileDeleteError",
]
