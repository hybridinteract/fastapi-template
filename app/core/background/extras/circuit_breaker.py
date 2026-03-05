"""
Circuit Breaker Pattern for External Service Calls

This module implements the circuit breaker pattern to prevent cascade failures
when external services (email, SMS, payment gateways) become unavailable.

Circuit Breaker States:
- CLOSED: Normal operation, requests go through
- OPEN: Service is down, fail fast without attempting
- HALF_OPEN: Testing if service recovered, allow limited requests

Benefits:
- Prevents resource exhaustion
- Faster failure detection
- Automatic recovery testing
- Better error messages to users

Usage:
    from app.core.background.extras import CircuitBreaker

    email_breaker = CircuitBreaker(
        name="email_service",
        failure_threshold=5,
        recovery_timeout=300
    )

    def send_email_task(ctx: TaskContext, ...):
        try:
            result = email_breaker.call(send_email, to=..., subject=...)
            return ctx.success_result(sent=True)
        except CircuitBreakerOpen:
            ctx.log_warning("Email service unavailable")
            raise ctx.non_retriable_error("Email service temporarily unavailable")
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, TypeVar, Dict, Optional
from threading import Lock
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Service down, fail fast
    HALF_OPEN = "half_open"    # Testing recovery


class CircuitBreakerOpen(Exception):
    """
    Exception raised when circuit breaker is open.

    This indicates the external service is unavailable and
    the request was not attempted to prevent cascade failures.
    """
    pass


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    Automatically opens circuit when service is down and closes
    when service recovers, preventing cascade failures.

    IMPORTANT: Per-Worker State Limitation
    --------------------------------------
    This circuit breaker maintains state **per worker process**. In a multi-worker
    Celery deployment, each worker has its own independent circuit breaker state.

    This means:
    - Worker A may have circuit OPEN while Worker B has circuit CLOSED
    - Each worker independently tracks failures and opens its circuit
    - State is not shared across workers

    When this is acceptable:
    - Single worker deployments
    - When eventual consistency is acceptable (all workers will eventually open)
    - When external service outages are prolonged (workers converge quickly)

    When you need Redis-backed circuit breaker:
    - Critical external services requiring immediate circuit opening
    - Short intermittent failures that may not be caught by all workers
    - Strict circuit breaker semantics required

    Attributes:
        name: Identifier for this circuit breaker (for logging)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
        success_threshold: Number of successes in HALF_OPEN before closing circuit
    """

    # Class-level storage for circuit breakers (singleton pattern)
    _instances: Dict[str, 'CircuitBreaker'] = {}
    _lock = Lock()

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for logging and metrics
            failure_threshold: Failures before opening circuit (default: 5)
            recovery_timeout: Seconds before testing recovery (default: 300)
            success_threshold: Successes in HALF_OPEN before closing (default: 2)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()

        # Thread safety for concurrent tasks
        self._state_lock = Lock()

        logger.info(
            f"Circuit breaker '{name}' initialized",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    @classmethod
    def get_instance(cls, name: str, **kwargs) -> 'CircuitBreaker':
        """
        Get or create circuit breaker instance (singleton per name).

        This ensures all tasks use the same circuit breaker instance
        for a given external service.

        Args:
            name: Circuit breaker identifier
            **kwargs: Configuration passed to __init__ if creating new instance

        Returns:
            CircuitBreaker instance
        """
        with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = cls(name=name, **kwargs)
            return cls._instances[name]

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func(*args, **kwargs)

        Raises:
            CircuitBreakerOpen: If circuit is open (service unavailable)
            Exception: Any exception raised by func

        Example:
            result = breaker.call(send_email, to="user@example.com", subject="Hello")
        """
        with self._state_lock:
            current_state = self.state

            # Check if we should attempt request
            if current_state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN - failing fast",
                        failure_count=self.failure_count,
                        last_failure=self.last_failure_time.isoformat() if self.last_failure_time else None
                    )
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.name}' is OPEN - service unavailable"
                    )

        # Attempt the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Handle successful call."""
        with self._state_lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.info(
                    f"Circuit breaker '{self.name}' success in HALF_OPEN",
                    success_count=self.success_count,
                    success_threshold=self.success_threshold
                )

                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                if self.failure_count > 0:
                    logger.info(
                        f"Circuit breaker '{self.name}' success - resetting failure count",
                        previous_failures=self.failure_count
                    )
                    self.failure_count = 0

    def _on_failure(self, exception: Exception):
        """Handle failed call."""
        with self._state_lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()

            logger.warning(
                f"Circuit breaker '{self.name}' failure",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
                state=self.state.value,
                error=str(exception),
                error_type=type(exception).__name__
            )

            if self.state == CircuitState.HALF_OPEN:
                # Failure in HALF_OPEN means service still down
                logger.warning(
                    f"Circuit breaker '{self.name}' failed in HALF_OPEN - reopening"
                )
                self._transition_to_open()
                self.success_count = 0

            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    logger.error(
                        f"Circuit breaker '{self.name}' threshold reached - opening circuit",
                        failure_count=self.failure_count,
                        threshold=self.failure_threshold
                    )
                    self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to test recovery."""
        if not self.last_failure_time:
            return True

        elapsed = datetime.utcnow() - self.last_failure_time
        should_reset = elapsed >= timedelta(seconds=self.recovery_timeout)

        if should_reset:
            logger.info(
                f"Circuit breaker '{self.name}' recovery timeout elapsed - testing recovery",
                elapsed_seconds=elapsed.total_seconds(),
                recovery_timeout=self.recovery_timeout
            )

        return should_reset

    def _transition_to_closed(self):
        """Transition to CLOSED state (service recovered)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()

        logger.info(
            f"Circuit breaker '{self.name}' CLOSED - service recovered",
            state="CLOSED"
        )

    def _transition_to_open(self):
        """Transition to OPEN state (service down)."""
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.utcnow()

        logger.error(
            f"Circuit breaker '{self.name}' OPEN - service unavailable",
            state="OPEN",
            failure_count=self.failure_count
        )

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state (testing recovery)."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.last_state_change = datetime.utcnow()

        logger.info(
            f"Circuit breaker '{self.name}' HALF_OPEN - testing recovery",
            state="HALF_OPEN"
        )

    def get_state(self) -> dict:
        """
        Get current circuit breaker state for monitoring.

        Returns:
            dict: Current state information
        """
        with self._state_lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "failure_threshold": self.failure_threshold,
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
                "last_state_change": self.last_state_change.isoformat(),
            }


# Export public API
__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
]
