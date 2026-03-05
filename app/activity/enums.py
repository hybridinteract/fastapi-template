"""
Activity action enums.

These are the standard action types for the audit log system.
Extend with project-specific actions in your feature module's
own enums.py if needed.
"""

from enum import Enum


class ActivityAction(str, Enum):
    """Standard actions tracked across the system."""

    # ── Core CRUD ──
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # ── State transitions ──
    STATUS_CHANGE = "STATUS_CHANGE"
    PUBLISH = "PUBLISH"
    ARCHIVE = "ARCHIVE"

    # ── Assignment ──
    ASSIGN = "ASSIGN"
    UNASSIGN = "UNASSIGN"

    # ── Auth ──
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"

    # ── Bulk / data operations ──
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"

    # ──── Project-Specific ────
    # Add custom action values here or in your feature module's own enums.py
    # Example:
    # SUBMIT     = "SUBMIT"
    # APPROVE    = "APPROVE"
    # REJECT     = "REJECT"
