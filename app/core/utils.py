"""
Core utility functions for the application.

These utilities are used across multiple modules.
"""

from datetime import UTC, datetime


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
    return datetime.now(UTC)


def escape_like(value: str) -> str:
    """
    Escape ``%`` and ``_`` so user input matches literally inside a LIKE / ILIKE pattern.

    Both are wildcards, so without this a search for ``50%`` or ``a_b`` matches far more
    than it says. Escapes with a backslash — PostgreSQL's default LIKE escape character —
    escaping the backslash itself first. Add your own wildcards around the result.

    Example:
        User.email.ilike(f"%{escape_like(search)}%")
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
