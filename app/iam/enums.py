from enum import StrEnum


class UserStatus(StrEnum):
    """Enum for user account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
