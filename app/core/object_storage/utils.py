"""
Utility functions for file validation, processing, and path generation.

Modern, functional approach using standard library and Pillow.
"""

import hashlib
import mimetypes
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import uuid4

from PIL import Image, ImageOps

from app.core.settings import get_settings

from .exceptions import (
    FileSizeError,
    FileTypeError,
    FileValidationError,
)


def validate_file(
    file: BinaryIO,
    filename: str,
    *,
    max_size: int | None = None,
    allowed_types: list[str] | None = None,
) -> dict:
    """
    Validate file size and type.

    Args:
        file: File object to validate
        filename: Original filename
        max_size: Maximum file size in bytes (default from settings)
        allowed_types: List of allowed MIME types (default from settings)

    Returns:
        dict: Validation results with file info

    Raises:
        FileSizeError: If file exceeds size limit
        FileTypeError: If file type not allowed
        FileValidationError: If file is invalid
    """
    settings = get_settings()

    # Get file size
    if hasattr(file, "seek"):
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset
    else:
        # Fallback if file isn't seekable
        size = 0 

    # Validate size
    max_size = max_size or settings.max_file_size_bytes
    if size > max_size:
        raise FileSizeError(filename, size, max_size)

    if size == 0:
        raise FileValidationError(filename, "File is empty")

    # Detect MIME type
    mime_type = detect_mime_type(file, filename)

    # Validate type
    allowed_types = allowed_types or settings.ALLOWED_DOCUMENT_TYPES
    if mime_type not in allowed_types:
        raise FileTypeError(filename, mime_type, allowed_types)

    # Additional validation for images
    is_image = mime_type.startswith("image/")
    if is_image:
        validate_image(file, filename)

    return {
        "filename": filename,
        "size": size,
        "mime_type": mime_type,
        "is_image": is_image,
    }


def detect_mime_type(file: BinaryIO, filename: str) -> str:
    """
    Detect MIME type using file content and extension.

    Args:
        file: File object to detect type for
        filename: Filename with extension

    Returns:
        str: Detected MIME type
    """
    # Try Pillow for images first
    try:
        if hasattr(file, "tell"):
            current_pos = file.tell()
            with Image.open(file) as img:
                format_to_mime = {
                    "JPEG": "image/jpeg",
                    "PNG": "image/png",
                    "WEBP": "image/webp",
                    "GIF": "image/gif",
                    "BMP": "image/bmp",
                }
                if hasattr(file, "seek"):
                    file.seek(current_pos)
                return format_to_mime.get(img.format, "application/octet-stream")
    except Exception:
        if hasattr(file, "seek"):
            file.seek(0)

    # Fallback to mimetypes based on extension
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def validate_image(file: BinaryIO, filename: str) -> None:
    """
    Validate image file integrity and dimensions.

    Args:
        file: Image file object
        filename: Original filename

    Raises:
        FileValidationError: If image validation fails
    """
    settings = get_settings()

    try:
        if hasattr(file, "tell"):
            current_pos = file.tell()
            
        with Image.open(file) as img:
            # Check dimensions
            width, height = img.size

            if (
                width > settings.MAX_IMAGE_WIDTH
                or height > settings.MAX_IMAGE_HEIGHT
            ):
                raise FileValidationError(
                    filename,
                    f"Image {width}x{height}px exceeds maximum "
                    f"{settings.MAX_IMAGE_WIDTH}x{settings.MAX_IMAGE_HEIGHT}px",
                )

            # Verify image integrity
            img.verify()

        if hasattr(file, "seek"):
            file.seek(current_pos)

    except FileValidationError:
        raise
    except Exception as e:
        raise FileValidationError(filename, f"Invalid image: {e}")


def process_image(
    file: BinaryIO,
    filename: str,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
    quality: int = 85,
    format: str | None = None,
) -> tuple[BytesIO, str, str]:
    """
    Process and optimize image file.

    Args:
        file: Image file object
        filename: Original filename
        max_width: Maximum width (default from settings)
        max_height: Maximum height (default from settings)
        quality: JPEG/WebP quality (1-100)
        format: Output format ('JPEG', 'PNG', 'WEBP', or None for auto)

    Returns:
        tuple: (processed_file, new_filename, mime_type)

    Raises:
        FileValidationError: If processing fails
    """
    settings = get_settings()
    max_width = max_width or settings.MAX_IMAGE_WIDTH
    max_height = max_height or settings.MAX_IMAGE_HEIGHT

    try:
        if hasattr(file, "seek"):
            file.seek(0)
        with Image.open(file) as img:
            # Auto-orient based on EXIF
            img = ImageOps.exif_transpose(img)

            # Convert RGBA to RGB for JPEG
            if format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode == "RGBA":
                    rgb_img.paste(img, mask=img.split()[-1])
                    img = rgb_img

            # Resize if needed
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height),
                              Image.Resampling.LANCZOS)

            # Auto-detect format if not specified
            if not format:
                format = "PNG" if img.mode == "RGBA" else "JPEG"

            # Save to bytes
            output = BytesIO()
            save_kwargs = {"format": format}

            if format == "JPEG":
                save_kwargs.update(
                    {
                        "quality": quality,
                        "optimize": True,
                        "progressive": True,
                    }
                )
            elif format == "PNG":
                save_kwargs["optimize"] = True
            elif format == "WEBP":
                save_kwargs.update({"quality": quality, "method": 6})

            img.save(output, **save_kwargs)
            output.seek(0)

            # Generate new filename
            stem = Path(filename).stem
            ext = format.lower().replace("jpeg", "jpg")
            new_filename = f"{stem}.{ext}"

            # Get MIME type
            mime_types = {
                "JPEG": "image/jpeg",
                "PNG": "image/png",
                "WEBP": "image/webp",
            }
            mime_type = mime_types.get(format, "image/jpeg")

            return output, new_filename, mime_type

    except Exception as e:
        raise FileValidationError(filename, f"Image processing failed: {e}")


def generate_key(
    filename: str,
    *,
    prefix: str = "uploads",
    use_date_structure: bool = True,
    unique_suffix: bool = True
) -> str:
    """
    Generate organized storage key/path for files.

    Args:
        filename: Original filename
        prefix: Directory prefix (e.g. 'users/avatars', 'details')
        use_date_structure: Whether to split by YYYY/MM/DD
        unique_suffix: Add random UUID suffix to prevent collisions

    Returns:
        str: Generated storage key
    
    Examples:
        >>> generate_key("image.png", prefix="users")
        'users/2026/02/12/image_a1b2c3d4.png'
    """
    # Generate unique ID and timestamp
    unique_id = uuid4().hex[:8] if unique_suffix else ""
    now = datetime.now(timezone.utc)
    
    path_obj = Path(filename)
    stem = path_obj.stem
    ext = path_obj.suffix.lower()

    # Build path components
    parts = []
    
    if prefix:
        parts.extend(prefix.strip("/").split("/"))

    if use_date_structure:
        parts.extend([now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")])

    # Construct final filename
    if unique_suffix:
        final_name = f"{stem}_{unique_id}{ext}"
    else:
        final_name = f"{stem}{ext}"
        
    parts.append(final_name)

    return "/".join(parts)


def calculate_hash(file: BinaryIO, algorithm: str = "sha256") -> str:
    """
    Calculate hash of file content.

    Args:
        file: File object
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')

    Returns:
        str: Hexadecimal hash string
    """
    hasher = hashlib.new(algorithm)

    if hasattr(file, "seek"):
        file.seek(0)
        while chunk := file.read(8192):
            hasher.update(chunk)
        file.seek(0)
    else:
        # If not seekable, we might be consuming it.
        while chunk := file.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()


def verify_hash(file: BinaryIO, expected_hash: str, algorithm: str = "sha256") -> bool:
    """
    Verify file integrity using hash comparison.

    Args:
        file: File object
        expected_hash: Expected hash value
        algorithm: Hash algorithm used

    Returns:
        bool: True if hashes match
    """
    actual_hash = calculate_hash(file, algorithm)
    return actual_hash.lower() == expected_hash.lower()
