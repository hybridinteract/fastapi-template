"""
Generic object storage service using boto3 for S3-compatible storage.

This module provides a clean interface for file operations with
any S3-compatible storage service (AWS S3, DigitalOcean Spaces, MinIO, etc.).
"""

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import BinaryIO, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.settings import get_settings

from .exceptions import (
    FileDeleteError,
    FileNotFoundError,
    FileUploadError,
    StorageConnectionError,
    StorageException,
)

logger = logging.getLogger(__name__)


class StorageService:
    """
    Generic object storage service using boto3.

    Handles file upload, download, deletion, and URL generation for
    S3-compatible storage providers.
    """

    def __init__(self) -> None:
        """Initialize storage service with settings from environment."""
        self.settings = get_settings()
        self._s3_client = None
        self.bucket = self.settings.DO_SPACES_BUCKET_NAME
        self.region = self.settings.DO_SPACES_REGION

    @property
    def s3(self):
        """Lazy-initialized S3 client with connection pooling."""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.settings.DO_SPACES_ENDPOINT_URL,
                    aws_access_key_id=self.settings.DO_SPACES_ACCESS_KEY_ID,
                    aws_secret_access_key=self.settings.DO_SPACES_SECRET_ACCESS_KEY,
                    region_name=self.region,
                    config=Config(
                        signature_version="s3v4",
                        s3={"addressing_style": "virtual"},
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                )
                logger.info("S3 client initialized successfully")
            except NoCredentialsError:
                logger.error("Invalid storage credentials")
                raise StorageConnectionError("Invalid storage credentials")
            except Exception as e:
                logger.error(f"Failed to initialize storage: {e}")
                raise StorageConnectionError(
                    f"Storage initialization failed: {e}")

        return self._s3_client

    def upload(
        self,
        file: BinaryIO,
        key: str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        public: bool = False,
    ) -> str:
        """
        Upload file to storage.

        Args:
            file: File-like object to upload
            key: Storage path/key for the file
            content_type: MIME type of the file
            metadata: Optional metadata dict (keys must be lowercase)
            public: Make file publicly accessible

        Returns:
            str: URL to access the uploaded file

        Raises:
            FileUploadError: If upload fails
        """
        try:
            extra_args = {
                "ContentType": content_type,
                "Metadata": metadata or {},
            }

            if public:
                extra_args["ACL"] = "public-read"

            # Ensure file is at start
            if hasattr(file, "seek"):
                file.seek(0)

            # Upload to S3
            self.s3.upload_fileobj(
                Fileobj=file,
                Bucket=self.bucket,
                Key=key,
                ExtraArgs=extra_args,
            )

            # Return appropriate URL
            if public:
                url = self._get_public_url(key)
            else:
                url = self.generate_presigned_url(key)

            logger.info(f"File uploaded successfully: {key}")
            return url

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Upload failed for {key}: {error_code}")
            raise FileUploadError(key, f"S3 Error: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected upload error for {key}: {e}")
            raise FileUploadError(key, str(e))
        
    def save_file(self, key: str, content: bytes, content_type: str = "application/octet-stream", metadata: dict | None = None, public: bool = False) -> str:
        """
        Save a file bytes content to object storage.
        
        Args:
            key: Storage path/key for the file
            content: File content as bytes
            content_type: MIME type of the file
            metadata: Optional metadata dict
            public: Make file publicly accessible
            
        Returns:
            str: URL to access the uploaded file
        """
        import io
        file_obj = io.BytesIO(content)
        return self.upload(
            file=file_obj,
            key=key,
            content_type=content_type,
            metadata=metadata,
            public=public
        )

    def delete(self, key: str) -> bool:
        """
        Delete file from storage.

        Args:
            key: Storage path/key of file to delete

        Returns:
            bool: True if deletion successful

        Raises:
            FileDeleteError: If deletion fails
        """
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"File deleted successfully: {key}")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Delete failed for {key}: {error_code}")
            raise FileDeleteError(key, f"S3 Error: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected delete error for {key}: {e}")
            raise FileDeleteError(key, str(e))

    def exists(self, key: str) -> bool:
        """
        Check if file exists in storage.

        Args:
            key: Storage path/key to check

        Returns:
            bool: True if file exists
        """
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"Error checking file existence for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking file {key}: {e}")
            return False

    def get_metadata(self, key: str) -> dict:
        """
        Get file metadata from storage.

        Args:
            key: Storage path/key of file

        Returns:
            dict: File metadata including size, type, modified time

        Raises:
            FileNotFoundError: If file doesn't exist
            StorageException: If metadata retrieval fails
        """
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)

            return {
                "size": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
                "etag": response.get("ETag", "").strip('"'),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(key)
            logger.error(f"Error getting metadata for {key}: {e}")
            raise StorageException(f"Failed to get metadata: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting metadata for {key}: {e}")
            raise StorageException(f"Unexpected error: {e}")

    def generate_presigned_url(
        self,
        key: str,
        *,
        expiration: int = 3600,
        method: str = "get_object",
    ) -> str:
        """
        Generate temporary presigned URL for file access.

        Args:
            key: Storage path/key of file
            expiration: URL expiration in seconds (default 1 hour)
            method: HTTP method ('get_object' or 'put_object')

        Returns:
            str: Presigned URL

        Raises:
            StorageException: If URL generation fails
        """
        try:
            url = self.s3.generate_presigned_url(
                method,
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL for {key}: {e}")
            raise StorageException(f"Failed to generate URL: {e}")

    def generate_upload_url(
        self,
        key: str,
        *,
        content_type: str,
        expiration: int = 3600,
        max_size: int | None = None,
    ) -> dict:
        """
        Generate presigned POST URL for direct client upload.

        Args:
            key: Storage path/key for the file
            content_type: MIME type of file
            expiration: URL expiration in seconds (default 1 hour)
            max_size: Maximum file size in bytes (default from settings)

        Returns:
            dict: Presigned POST data with 'url' and 'fields'

        Raises:
            StorageException: If URL generation fails
        """
        if max_size is None:
            max_size = self.settings.max_file_size_bytes

        try:
            conditions = [
                {"Content-Type": content_type},
                ["content-length-range", 1, max_size],
            ]

            response = self.s3.generate_presigned_post(
                Bucket=self.bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=conditions,
                ExpiresIn=expiration,
            )

            return response
        except Exception as e:
            logger.error(f"Error generating upload URL for {key}: {e}")
            raise StorageException(f"Failed to generate upload URL: {e}")

    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> list[dict]:
        """
        List objects in storage with optional prefix filter.

        Args:
            prefix: Prefix to filter objects
            max_keys: Maximum number of objects to return

        Returns:
            list: List of object information dicts

        Raises:
            StorageException: If listing fails
        """
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            objects = []
            for obj in response.get("Contents", []):
                objects.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"].strip('"'),
                    }
                )

            return objects
        except Exception as e:
            logger.error(f"Error listing objects with prefix {prefix}: {e}")
            raise StorageException(f"Failed to list objects: {e}")

    def health_check(self) -> dict:
        """
        Check storage service health.

        Returns:
            dict: Health check results with status and details
        """
        start = datetime.now(timezone.utc)

        try:
            # Simple head_bucket check
            self.s3.head_bucket(Bucket=self.bucket)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()

            return {
                "status": "healthy",
                "message": "Storage connection successful",
                "response_time": elapsed,
                "bucket": self.bucket,
                "region": self.region,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except ClientError as e:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            error_code = e.response["Error"]["Code"]

            return {
                "status": "unhealthy",
                "message": f"Storage check failed: {error_code}",
                "response_time": elapsed,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()

            return {
                "status": "unhealthy",
                "message": "Storage check failed",
                "response_time": elapsed,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _get_public_url(self, key: str) -> str:
        """Get public URL for a file (CDN or direct)."""
        if self.settings.S3_PUBLIC_DOMAIN:
            # Handle trailing slash in public domain
            base_url = self.settings.S3_PUBLIC_DOMAIN.rstrip("/")
            return f"{base_url}/{key}"
        # Fallback to endpoint/bucket style if no public domain configured
        # This is a best-effort fallback
        return f"{self.settings.DO_SPACES_ENDPOINT_URL}/{self.bucket}/{key}"


@lru_cache()
def get_storage() -> StorageService:
    """
    Get cached storage service instance.

    Returns:
        StorageService: Singleton storage service instance
    """
    return StorageService()

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.settings import get_settings

from .exceptions import (
    FileDeleteError,
    FileNotFoundError,
    FileUploadError,
    StorageConnectionError,
    StorageException,
)

logger = logging.getLogger(__name__)


class StorageService:

    """
    Simple, modern object storage service using boto3.

    Handles file upload, download, deletion, and URL generation for
    S3-compatible storage providers like DigitalOcean Spaces.
    """

    def __init__(self) -> None:
        """Initialize storage service with settings from environment."""
        self.settings = get_settings()
        self._s3_client = None
        self.bucket = self.settings.DO_SPACES_BUCKET_NAME
        self.region = self.settings.DO_SPACES_REGION

    @property
    def s3(self):
        """Lazy-initialized S3 client with connection pooling."""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.settings.DO_SPACES_ENDPOINT_URL,
                    aws_access_key_id=self.settings.DO_SPACES_ACCESS_KEY_ID,
                    aws_secret_access_key=self.settings.DO_SPACES_SECRET_ACCESS_KEY,
                    region_name=self.region,
                    config=Config(
                        signature_version="s3v4",
                        s3={"addressing_style": "virtual"},
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                )
                logger.info("S3 client initialized successfully")
            except NoCredentialsError:
                logger.error("Invalid storage credentials")
                raise StorageConnectionError("Invalid storage credentials")
            except Exception as e:
                logger.error(f"Failed to initialize storage: {e}")
                raise StorageConnectionError(
                    f"Storage initialization failed: {e}")

        return self._s3_client

    def upload(
        self,
        file: BinaryIO,
        key: str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        public: bool = False,
    ) -> str:
        """
        Upload file to storage.

        Args:
            file: File-like object to upload
            key: Storage path/key for the file
            content_type: MIME type of the file
            metadata: Optional metadata dict (keys must be lowercase)
            public: Make file publicly accessible

        Returns:
            str: URL to access the uploaded file

        Raises:
            FileUploadError: If upload fails
        """
        try:
            extra_args = {
                "ContentType": content_type,
                "Metadata": metadata or {},
            }

            if public:
                extra_args["ACL"] = "public-read"

            # Ensure file is at start
            file.seek(0)

            # Upload to S3
            self.s3.upload_fileobj(
                Fileobj=file,
                Bucket=self.bucket,
                Key=key,
                ExtraArgs=extra_args,
            )

            # Return appropriate URL
            if public:
                url = self._get_public_url(key)
            else:
                url = self.generate_presigned_url(key)

            logger.info(f"File uploaded successfully: {key}")
            return url

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Upload failed for {key}: {error_code}")
            raise FileUploadError(key, f"S3 Error: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected upload error for {key}: {e}")
            raise FileUploadError(key, str(e))
        
    def save_file(self, key: str, content: bytes, content_type: str = "application/octet-stream", metadata: dict | None = None, public: bool = False) -> str:
        """
        Save a file to object storage. Compatible with resume upload interface.
        Args:
            key: Storage path/key for the file
            content: File content as bytes
            content_type: MIME type of the file
            metadata: Optional metadata dict
            public: Make file publicly accessible
        Returns:
            str: URL to access the uploaded file
        """
        import io
        file_obj = io.BytesIO(content)
        return self.upload(
            file=file_obj,
            key=key,
            content_type=content_type,
            metadata=metadata,
            public=public
        )

    def delete(self, key: str) -> bool:
        """
        Delete file from storage.

        Args:
            key: Storage path/key of file to delete

        Returns:
            bool: True if deletion successful

        Raises:
            FileDeleteError: If deletion fails
        """
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"File deleted successfully: {key}")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Delete failed for {key}: {error_code}")
            raise FileDeleteError(key, f"S3 Error: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected delete error for {key}: {e}")
            raise FileDeleteError(key, str(e))

    def exists(self, key: str) -> bool:
        """
        Check if file exists in storage.

        Args:
            key: Storage path/key to check

        Returns:
            bool: True if file exists
        """
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"Error checking file existence for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking file {key}: {e}")
            return False

    def get_metadata(self, key: str) -> dict:
        """
        Get file metadata from storage.

        Args:
            key: Storage path/key of file

        Returns:
            dict: File metadata including size, type, modified time

        Raises:
            FileNotFoundError: If file doesn't exist
            StorageException: If metadata retrieval fails
        """
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)

            return {
                "size": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
                "etag": response.get("ETag", "").strip('"'),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(key)
            logger.error(f"Error getting metadata for {key}: {e}")
            raise StorageException(f"Failed to get metadata: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting metadata for {key}: {e}")
            raise StorageException(f"Unexpected error: {e}")

    def generate_presigned_url(
        self,
        key: str,
        *,
        expiration: int | None = None,
        method: str = "get_object",
    ) -> str:
        """
        Generate temporary presigned URL for file access.

        Args:
            key: Storage path/key of file
            expiration: URL expiration in seconds (default from settings)
            method: HTTP method ('get_object' or 'put_object')

        Returns:
            str: Presigned URL

        Raises:
            StorageException: If URL generation fails
        """
        if expiration is None:
            expiration = self.settings.DOCUMENT_URL_EXPIRY_HOURS * 3600

        try:
            url = self.s3.generate_presigned_url(
                method,
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL for {key}: {e}")
            raise StorageException(f"Failed to generate URL: {e}")

    def generate_upload_url(
        self,
        key: str,
        *,
        content_type: str,
        expiration: int = 3600,
        max_size: int | None = None,
    ) -> dict:
        """
        Generate presigned POST URL for direct client upload.

        Args:
            key: Storage path/key for the file
            content_type: MIME type of file
            expiration: URL expiration in seconds (default 1 hour)
            max_size: Maximum file size in bytes (default from settings)

        Returns:
            dict: Presigned POST data with 'url' and 'fields'

        Raises:
            StorageException: If URL generation fails
        """
        if max_size is None:
            max_size = self.settings.max_file_size_bytes

        try:
            conditions = [
                {"Content-Type": content_type},
                ["content-length-range", 1, max_size],
            ]

            response = self.s3.generate_presigned_post(
                Bucket=self.bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=conditions,
                ExpiresIn=expiration,
            )

            return response
        except Exception as e:
            logger.error(f"Error generating upload URL for {key}: {e}")
            raise StorageException(f"Failed to generate upload URL: {e}")

    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> list[dict]:
        """
        List objects in storage with optional prefix filter.

        Args:
            prefix: Prefix to filter objects
            max_keys: Maximum number of objects to return

        Returns:
            list: List of object information dicts

        Raises:
            StorageException: If listing fails
        """
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            objects = []
            for obj in response.get("Contents", []):
                objects.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"].strip('"'),
                    }
                )

            return objects
        except Exception as e:
            logger.error(f"Error listing objects with prefix {prefix}: {e}")
            raise StorageException(f"Failed to list objects: {e}")

    def health_check(self) -> dict:
        """
        Check storage service health.

        Returns:
            dict: Health check results with status and details
        """
        start = datetime.now(timezone.utc)

        try:
            # Simple head_bucket check
            self.s3.head_bucket(Bucket=self.bucket)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()

            return {
                "status": "healthy",
                "message": "Storage connection successful",
                "response_time": elapsed,
                "bucket": self.bucket,
                "region": self.region,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except ClientError as e:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            error_code = e.response["Error"]["Code"]

            return {
                "status": "unhealthy",
                "message": f"Storage check failed: {error_code}",
                "response_time": elapsed,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()

            return {
                "status": "unhealthy",
                "message": "Storage check failed",
                "response_time": elapsed,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _get_public_url(self, key: str) -> str:
        """Get public URL for a file (CDN or direct)."""
        return f"{self.settings.spaces_public_url}/{key}"


@lru_cache()
def get_storage() -> StorageService:
    """
    Get cached storage service instance.

    Returns:
        StorageService: Singleton storage service instance
    """
    return StorageService()
