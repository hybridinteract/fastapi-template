"""
Application settings and configuration.

Uses Pydantic Settings for environment-based configuration
with validation and type checking.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Literal, List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_parse_none_str="null"
    )

    # ==================== Application Settings ====================
    APP_NAME: str = Field(default="MyApp",
                          description="Application name")
    APP_VERSION: str = Field(
        default="0.1.0", description="Application version")
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Current environment"
    )
    DEBUG: bool = Field(default=False, description="Debug mode")

    # ==================== API Settings ====================
    API_V1_PREFIX: str = Field(default="/api/v1", description="API v1 prefix")
    API_PORT: int = Field(default=8000, ge=1, le=65535, description="API port")
    HOST: str = Field(default="0.0.0.0", description="API host")

    # ==================== Database Settings ====================
    POSTGRES_USER: str = Field(..., description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    POSTGRES_HOST: str = Field(
        default="localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(
        default=5432, ge=1, le=65535, description="PostgreSQL port")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")

    # Database Pool Settings
    DB_POOL_SIZE: int = Field(
        default=5, ge=1, description="Connection pool size")
    DB_MAX_OVERFLOW: int = Field(
        default=10, ge=0, description="Max overflow connections")
    DB_POOL_TIMEOUT: int = Field(
        default=30, ge=1, description="Pool timeout in seconds")
    DB_ECHO: bool = Field(default=False, description="Echo SQL statements")

    # ==================== Security Settings ====================
    SECRET_KEY: str = Field(..., description="Secret key for signing")
    JWT_SECRET_KEY: str = Field(..., description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=120, ge=1)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    # ==================== CORS Settings ====================
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )
    CORS_ALLOW_METHODS: List[str] = Field(
        default=["*"],
        description="Allowed HTTP methods for CORS"
    )
    CORS_ALLOW_HEADERS: List[str] = Field(
        default=["*"],
        description="Allowed headers for CORS"
    )
    CORS_ORIGIN_REGEX: str = Field(
        default="",
        description="Regex pattern for CORS origin matching"
    )

    # ==================== Security Settings (Middleware) ====================
    TRUSTED_HOSTS: List[str] = Field(
        default=["*"],
        description="Trusted hosts for production (use specific domains in production)"
    )

    # ==================== Compression Settings ====================
    ENABLE_GZIP: bool = Field(
        default=True,
        description="Enable GZip compression for responses"
    )
    GZIP_MINIMUM_SIZE: int = Field(
        default=1000,
        ge=0,
        description="Minimum response size in bytes to trigger GZip compression"
    )

    # ==================== Redis Settings ====================
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database")
    REDIS_PASSWORD: str = Field(default="", description="Redis password")
    REDIS_MAX_CONNECTIONS: int = Field(
        default=10, ge=1, description="Max Redis connection pool size"
    )
    CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable Redis caching (set False to bypass cache entirely)"
    )

    # ==================== Logging Settings ====================
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    ENABLE_FILE_LOGGING: bool = Field(
        default=True,
        description="Enable logging to files"
    )
    LOG_FILE_MAX_SIZE: int = Field(
        default=10485760,  # 10MB
        description="Maximum size of log file in bytes before rotation"
    )
    LOG_FILE_BACKUP_COUNT: int = Field(
        default=5,
        description="Number of backup log files to keep"
    )

    # ==================== Object Storage Settings ====================
    DO_SPACES_BUCKET_NAME: str = Field(default="", description="DigitalOcean Spaces Bucket Name")
    DO_SPACES_REGION: str = Field(default="blr1", description="DigitalOcean Spaces Region")
    DO_SPACES_ENDPOINT_URL: str = Field(default="", description="DigitalOcean Spaces Endpoint URL")
    DO_SPACES_ACCESS_KEY_ID: str = Field(default="", description="DigitalOcean Spaces Access Key ID")
    DO_SPACES_SECRET_ACCESS_KEY: str = Field(default="", description="DigitalOcean Spaces Secret Access Key")
    # Kept generic for CDN/public access, but can map to DO_SPACES_CDN_ENDPOINT if desired
    S3_PUBLIC_DOMAIN: str = Field(default="", description="Public domain for assets (CDN)")

    # ==================== File Upload Settings ====================
    UPLOAD_MAX_SIZE_MB: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum file upload size in MB"
    )
    ALLOWED_DOCUMENT_TYPES: List[str] = Field(
        default=[
            # Images
            "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
            # Videos
            "video/mp4", "video/webm", "video/ogg", "video/quicktime",
            "video/x-msvideo", "video/x-ms-wmv",
            # Audio
            "audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", 
            "audio/m4a", "audio/webm", "audio/x-m4a", "audio/mp3",
            # Documents
            "application/pdf", "text/plain",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/rtf", "text/rtf",
            # Spreadsheets
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
        ],
        description="Allowed file MIME types"
    )
    MAX_IMAGE_WIDTH: int = Field(default=4096, description="Max image width")
    MAX_IMAGE_HEIGHT: int = Field(default=4096, description="Max image height")
    DOCUMENT_URL_EXPIRY_HOURS: int = Field(
        default=1,
        ge=1,
        le=168,
        description="Presigned URL expiry time in hours (max 7 days)"
    )

    # ==================== Celery Settings ====================

    # Task execution settings
    CELERY_TASK_TRACK_STARTED: bool = Field(
        default=True,
        description="Track when tasks are started"
    )
    CELERY_TASK_TIME_LIMIT: int = Field(
        default=300,
        description="Hard time limit for tasks in seconds"
    )
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(
        default=240,
        description="Soft time limit for tasks in seconds"
    )
    CELERY_TASK_ACKS_LATE: bool = Field(
        default=True,
        description="Acknowledge tasks after execution (not on receive)"
    )
    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = Field(
        default=True,
        description="Reject tasks if worker is lost"
    )
    CELERY_TASK_COMPRESSION: str = Field(
        default="",
        description="Task compression algorithm (gzip, bzip2, or empty)"
    )

    # Worker settings
    CELERY_WORKER_POOL: str = Field(
        default="prefork",
        description="Worker pool type (prefork, solo, threads)"
    )
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(
        default=4,
        description="Number of tasks to prefetch per worker"
    )
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(
        default=500,
        description="Max tasks before worker process restart"
    )
    CELERY_WORKER_LOST_WAIT: int = Field(
        default=10,
        description="Seconds to wait for lost worker"
    )

    # Broker settings
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP: bool = Field(
        default=True,
        description="Retry broker connection on startup"
    )
    CELERY_BROKER_CONNECTION_MAX_RETRIES: int = Field(
        default=10,
        description="Max broker connection retries"
    )

    # Result backend settings
    CELERY_RESULT_EXPIRES: int = Field(
        default=3600,
        description="Result expiration time in seconds"
    )
    CELERY_RESULT_BACKEND_THREAD_SAFE: bool = Field(
        default=True,
        description="Thread-safe result backend"
    )

    # Celery database pool settings (for async tasks)
    CELERY_DB_POOL_SIZE: int = Field(
        default=3,
        description="DB pool size per worker"
    )
    CELERY_DB_MAX_OVERFLOW: int = Field(
        default=5,
        description="Max overflow connections per worker"
    )
    CELERY_DB_POOL_RECYCLE: int = Field(
        default=1800,
        description="Connection recycle time in seconds"
    )

    # ==================== Computed Properties ====================
    @property
    def max_file_size_bytes(self) -> int:
        """Calculate max file size in bytes."""
        return self.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    @property
    def database_url(self) -> str:
        """Build async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def celery_broker_url(self) -> str:
        """Build Celery broker URL (Redis DB 0)."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def celery_result_backend(self) -> str:
        """Build Celery result backend URL (Redis DB 1)."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @field_validator("SECRET_KEY", "JWT_SECRET_KEY")
    @classmethod
    def validate_secret_keys(cls, v: str, info) -> str:
        """Validate secret keys meet minimum security requirements."""
        if not v or len(v) < 32:
            raise ValueError(
                f"{info.field_name} must be at least 32 characters")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
