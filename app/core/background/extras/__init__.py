"""
Background Task Framework - Extras

Optional components that can be imported when needed.
These are not included in the main background task exports.

Example:
    from app.core.background.extras import CircuitBreaker, CircuitBreakerOpen
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
]
