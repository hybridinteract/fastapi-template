"""
Core utility functions for the application.

These utilities are used across multiple modules.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get current UTC timestamp.

    Use this function as the default value for datetime columns in SQLAlchemy models.
    Ensures all timestamps are stored in UTC timezone.

    Returns:
        datetime: Current UTC timestamp with timezone info

    Example:
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            default=utc_now,
            nullable=False
        )
    """
    return datetime.now(timezone.utc)
