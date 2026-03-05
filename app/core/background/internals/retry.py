"""
Retry Policy Configurations

This module defines predefined retry policies for common task patterns.
These policies can be referenced by name in task decorators, making it
easy to apply consistent retry behavior across similar tasks.

Retry policies include:
- Max retry attempts
- Delay between retries
- Exponential backoff configuration
- Jitter to prevent thundering herd

Example:
    @simple_task(name="...", retry_policy="high_priority")
    def send_email(ctx: TaskContext, ...):
        pass
"""

from typing import Dict, Any
from .exceptions import NON_RETRIABLE_EXCEPTIONS


# Predefined retry policies
RETRY_POLICIES: Dict[str, Dict[str, Any]] = {
    "standard": {
        "max_retries": 3,
        "default_retry_delay": 60,  # 1 minute
        "autoretry_for": (Exception,),
        "dont_autoretry_for": NON_RETRIABLE_EXCEPTIONS,
        "retry_backoff": True,
        "retry_backoff_max": 300,  # 5 minutes max delay
        "retry_jitter": True,
    },
    "aggressive": {
        "max_retries": 5,
        "default_retry_delay": 30,  # 30 seconds
        "autoretry_for": (Exception,),
        "dont_autoretry_for": NON_RETRIABLE_EXCEPTIONS,
        "retry_backoff": True,
        "retry_backoff_max": 600,  # 10 minutes max delay
        "retry_jitter": True,
    },
    "high_priority": {
        "max_retries": 3,
        "default_retry_delay": 120,  # 2 minutes
        "autoretry_for": (Exception,),
        "dont_autoretry_for": NON_RETRIABLE_EXCEPTIONS,
        "retry_backoff": True,
        "retry_backoff_max": 600,  # 10 minutes max delay
        "retry_jitter": True,
    },
    "long_running": {
        "max_retries": 2,
        "default_retry_delay": 300,  # 5 minutes
        "autoretry_for": (Exception,),
        "dont_autoretry_for": NON_RETRIABLE_EXCEPTIONS,
        "retry_backoff": True,
        "retry_backoff_max": 900,  # 15 minutes max delay
        "retry_jitter": True,
    },
    "no_retry": {
        "max_retries": 0,
    },
}


def get_retry_policy(policy_name: str) -> Dict[str, Any]:
    """
    Get retry policy configuration by name.

    Args:
        policy_name: Name of the retry policy (e.g., "standard", "aggressive")

    Returns:
        Dict containing Celery retry configuration

    Raises:
        KeyError: If policy_name is not found

    Example:
        retry_config = get_retry_policy("standard")
        # Returns: {"max_retries": 3, "default_retry_delay": 60, ...}
    """
    if policy_name not in RETRY_POLICIES:
        available = ", ".join(RETRY_POLICIES.keys())
        raise KeyError(
            f"Unknown retry policy '{policy_name}'. "
            f"Available policies: {available}"
        )
    return RETRY_POLICIES[policy_name].copy()


# Export public API
__all__ = [
    "RETRY_POLICIES",
    "get_retry_policy",
]
