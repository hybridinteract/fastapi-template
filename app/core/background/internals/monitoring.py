"""
Task Monitoring and Metrics

This module provides utilities for tracking task performance, success rates,
and execution patterns. This is essential for:
- Debugging production task failures
- Identifying performance bottlenecks
- Monitoring system health
- Capacity planning

Metrics tracked:
- Task execution duration
- Success/failure counts
- Retry patterns
- Validation error rates

Integration points:
- Currently logs metrics (can be parsed by log aggregation tools)
- Designed to integrate with Prometheus/StatsD/CloudWatch in the future
"""

import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskMetrics:
    """
    Container for task execution metrics.

    Tracks various metrics during task execution that can be
    logged or exported to monitoring systems.

    Attributes:
        task_name: Name of the Celery task
        task_id: Unique task execution ID
        start_time: Task start timestamp (seconds since epoch)
        end_time: Task end timestamp (optional)
        duration: Task execution duration in seconds (optional)
        success: Whether task completed successfully
        retry_count: Number of retries before success/failure
        error_type: Type of exception if task failed
        custom_metrics: Dict of custom metrics specific to the task
    """
    task_name: str
    task_id: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: Optional[bool] = None
    retry_count: int = 0
    error_type: Optional[str] = None
    custom_metrics: Dict[str, Any] = field(default_factory=dict)

    def mark_success(self):
        """Mark task as successfully completed and calculate duration."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = True
        self._log_completion()

    def mark_failure(self, error: Exception):
        """
        Mark task as failed and calculate duration.

        Args:
            error: The exception that caused the failure
        """
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = False
        self.error_type = type(error).__name__
        self._log_completion()

    def add_custom_metric(self, name: str, value: Any):
        """
        Add a custom metric specific to this task execution.

        Args:
            name: Metric name
            value: Metric value

        Example:
            metrics.add_custom_metric("emails_sent", 10)
            metrics.add_custom_metric("processing_errors", 2)
        """
        self.custom_metrics[name] = value

    def _log_completion(self):
        """Log task completion metrics."""
        status = "SUCCESS" if self.success else "FAILURE"
        logger.info(
            f"Task {status}: {self.task_name}",
            extra={
                "task_id": self.task_id,
                "task_name": self.task_name,
                "duration_seconds": self.duration,
                "success": self.success,
                "retry_count": self.retry_count,
                "error_type": self.error_type,
                "metric_type": "task_completion",
                **self.custom_metrics
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Export metrics as dictionary.

        Returns:
            Dict containing all metrics

        Example:
            metrics_dict = metrics.to_dict()
            # Send to external monitoring system
        """
        return {
            "task_name": self.task_name,
            "task_id": self.task_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "success": self.success,
            "retry_count": self.retry_count,
            "error_type": self.error_type,
            **self.custom_metrics
        }


class Timer:
    """
    Simple timer for measuring operation durations within tasks.

    Example:
        timer = Timer("database_query")
        # ... perform query ...
        duration = timer.stop()
    """

    def __init__(self, name: str):
        """
        Initialize timer.

        Args:
            name: Name/label for this timer
        """
        self.name = name
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None

    def stop(self) -> float:
        """
        Stop timer and return duration.

        Returns:
            Duration in seconds
        """
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        return self.duration

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically stop timer."""
        self.stop()
        return False


class StatsCounter:
    """
    Simple counter for tracking statistics during batch operations.

    Example:
        stats = StatsCounter()
        for item in items:
            if process(item):
                stats.increment("processed")
            else:
                stats.increment("failed")
        print(stats.to_dict())  # {"processed": 100, "failed": 5}
    """

    def __init__(self):
        """Initialize empty stats counter."""
        self._counts: Dict[str, int] = {}

    def increment(self, key: str, amount: int = 1):
        """
        Increment counter by given amount.

        Args:
            key: Counter key/name
            amount: Amount to increment (default: 1)
        """
        self._counts[key] = self._counts.get(key, 0) + amount

    def get(self, key: str, default: int = 0) -> int:
        """
        Get counter value.

        Args:
            key: Counter key
            default: Default value if key doesn't exist

        Returns:
            Counter value
        """
        return self._counts.get(key, default)

    def to_dict(self) -> Dict[str, int]:
        """
        Export all counters as dictionary.

        Returns:
            Dict of all counter values
        """
        return self._counts.copy()

    def __repr__(self):
        """String representation of stats."""
        return f"StatsCounter({self._counts})"


def log_metric(metric_name: str, value: Any, **tags):
    """
    Log a metric with optional tags.

    This is a simple metric logging function that outputs to logs.
    Can be replaced with actual metrics backend (Prometheus, StatsD) later.

    Args:
        metric_name: Name of the metric
        value: Metric value
        **tags: Additional tags/labels for the metric

    Example:
        log_metric("task.duration", 1.5, task_name="send_email", status="success")
        log_metric("task.retry_count", 2, task_name="process_payment")
    """
    logger.info(
        f"METRIC: {metric_name}={value}",
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_type": "gauge",
            **tags
        }
    )


# Export public API
__all__ = [
    "TaskMetrics",
    "Timer",
    "StatsCounter",
    "log_metric",
]
