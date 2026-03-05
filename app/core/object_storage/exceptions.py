"""
Object Storage exceptions.

Custom exceptions for object storage operations.
"""


class StorageException(Exception):
    """Base exception for storage operations."""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class FileUploadError(StorageException):
    """Exception raised when file upload fails."""
    
    def __init__(self, filename: str, reason: str = "Upload failed"):
        self.filename = filename
        self.reason = reason
        super().__init__(f"Failed to upload file '{filename}': {reason}")


class FileValidationError(StorageException):
    """Exception raised when file validation fails."""
    
    def __init__(self, filename: str, reason: str):
        self.filename = filename
        self.reason = reason
        super().__init__(f"File validation failed for '{filename}': {reason}")


class FileSizeError(FileValidationError):
    """Exception raised when file size exceeds limits."""
    
    def __init__(self, filename: str, size: int, max_size: int):
        self.filename = filename
        self.size = size
        self.max_size = max_size
        super().__init__(
            filename,
            f"File size {size} bytes exceeds maximum allowed size {max_size} bytes"
        )


class FileTypeError(FileValidationError):
    """Exception raised when file type is not allowed."""
    
    def __init__(self, filename: str, file_type: str, allowed_types: list):
        self.filename = filename
        self.file_type = file_type
        self.allowed_types = allowed_types
        super().__init__(
            filename,
            f"File type '{file_type}' not allowed. Allowed types: {', '.join(allowed_types)}"
        )


class StorageConnectionError(StorageException):
    """Exception raised when storage connection fails."""
    
    def __init__(self, reason: str = "Connection failed"):
        super().__init__(f"Storage connection error: {reason}")


class FileNotFoundError(StorageException):
    """Exception raised when file is not found in storage."""
    
    def __init__(self, file_key: str):
        self.file_key = file_key
        super().__init__(f"File not found: {file_key}")


class FileDeleteError(StorageException):
    """Exception raised when file deletion fails."""
    
    def __init__(self, file_key: str, reason: str = "Deletion failed"):
        self.file_key = file_key
        self.reason = reason
        super().__init__(f"Failed to delete file '{file_key}': {reason}")