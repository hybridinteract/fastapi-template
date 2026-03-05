# Background Task Framework

A lean, production-ready Celery framework for async database operations in FastAPI.

## Quick Start

### 1. Create `tasks.py` in Your Module

```python
# app/your_module/tasks.py
from app.core.background import simple_task, db_task, TaskContext

@simple_task(name="your_module.send_notification", retry_policy="standard")
def send_notification(ctx: TaskContext, user_id: str, message: str):
    ctx.log_info(f"Sending notification to {user_id}")
    # ... your logic ...
    return ctx.success_result(sent=True)

@db_task(name="your_module.process_entity", retry_policy="standard")
async def process_entity(ctx: TaskContext, entity_id: str):
    entity = await entity_crud.get(ctx.session, entity_id)
    # ... process entity ...
    # Auto-commits on success
    return ctx.success_result(entity_id=entity_id)
```

### 2. Trigger the Task

```python
from app.your_module.tasks import send_notification
send_notification.delay(user_id="uuid", message="Hello")
```

Tasks are auto-discovered from `tasks.py` files.

---

## Decorators

### `@simple_task` - No Database Access

```python
@simple_task(
    name="module.task_name",      # Required: unique task identifier
    retry_policy="standard",       # standard|aggressive|high_priority|long_running|no_retry
    queue="default"                # default|high_priority|low_priority
)
def my_task(ctx: TaskContext, param1: str):
    ctx.log_info("Processing")
    return ctx.success_result(done=True)
```

**Use for:** Email sending, SMS, external API calls, webhooks

### `@db_task` - With Database Access

```python
@db_task(
    name="module.db_task_name",
    retry_policy="standard",
    queue="default"
)
async def my_db_task(ctx: TaskContext, entity_id: str):
    result = await some_crud.get(ctx.session, entity_id)
    # Auto-commits on success, auto-rollbacks on error
    return ctx.success_result(entity_id=entity_id)
```

**Use for:** Any task needing database read/write

---

## TaskContext API

Every task receives a `TaskContext` as the first parameter:

### Logging
```python
ctx.log_info("Message", extra_field=value)
ctx.log_success("Completed", count=10)
ctx.log_warning("Something concerning")
ctx.log_error("Failed", exc_info=True)
ctx.log_debug("Verbose info")
```

### Validation
```python
user_uuid = ctx.validate_uuid(user_id, "user_id")  # Raises TaskValidationError if invalid
```

### Exceptions (Non-Retriable)
```python
raise ctx.not_found_error("User not found", user_id=user_id)
raise ctx.validation_error("Invalid input", field="email")
raise ctx.config_error("Missing API key")
```

### Results
```python
return ctx.success_result(user_id=user_id, status="created")
# Returns: {"status": "success", "task_id": "...", "user_id": "...", "status": "created"}
```

---

## Batch Operations

Use `@db_task` with batch utilities for bulk operations:

```python
@db_task(
    name="module.bulk_update",
    retry_policy="long_running",
    queue="low_priority"
)
async def bulk_update(ctx: TaskContext, item_ids: list[str]):
    stats = ctx.create_stats_counter()

    async for batch in ctx.iter_batches(item_ids, item_crud, batch_size=50):
        for item in batch:
            # process item
            stats.increment("processed")
        await ctx.commit_batch()

    return ctx.success_result(**stats.to_dict())
```

**Batch utilities available in TaskContext:**
- `ctx.iter_batches(items, crud, batch_size=20)` - Iterate in batches
- `ctx.commit_batch()` - Commit current batch
- `ctx.create_stats_counter()` - Track processing stats
- `ctx.log_progress(**metrics)` - Log progress updates

---

## Queues & Retry Policies

### Queues

| Queue | Use For | Examples |
|-------|---------|----------|
| `high_priority` | Time-sensitive, user-facing | OTP, payment confirmation |
| `default` | Normal operations | Status updates, notifications |
| `low_priority` | Background, can wait | Cleanup, reports, batch jobs |

### Retry Policies

| Policy | Max Retries | Initial Delay | Use For |
|--------|-------------|---------------|---------|
| `standard` | 3 | 60s | Most tasks |
| `aggressive` | 5 | 30s | Critical tasks |
| `high_priority` | 3 | 120s | Time-sensitive |
| `long_running` | 2 | 300s | Batch operations |
| `no_retry` | 0 | - | Idempotency issues |

---

## Error Handling

### Non-Retriable Errors (No Retry)
- `TaskValidationError` - Invalid input
- `TaskNotFoundError` - Missing resource
- `TaskConfigurationError` - Misconfiguration
- `IntegrityError` - DB constraint violation

### Retriable Errors (Auto-Retry)
- `OperationalError` - Connection lost
- `TimeoutError` - Query timeout
- Unknown exceptions

---

## Task Deduplication

Prevent duplicate tasks using custom `task_id`:

```python
# Only one verification email per user at a time
send_verification_email.apply_async(
    args=(user_id, email, code),
    task_id=f"verify-email-{user_id}"
)
```

**Deduplication keys:**
- User notifications: `f"notify-{user_id}"`
- Entity updates: `f"update-{entity_id}"`
- Periodic tasks: `f"daily-{date}"`

---

## Testing

```python
from app.core.background import TaskTestContext, mock_task_session

async def test_my_db_task():
    ctx = TaskTestContext(
        task_id="test-123",
        session=mock_task_session()
    )

    result = await my_db_task(ctx, entity_id="uuid-here")

    assert result["status"] == "success"
    ctx.assert_logged_success()
```

---

## Optional: Circuit Breaker

For external service protection, import from extras:

```python
from app.core.background.extras import CircuitBreaker, CircuitBreakerOpen

email_breaker = CircuitBreaker(name="email_service", failure_threshold=5)

def send_email_task(ctx: TaskContext, ...):
    try:
        result = email_breaker.call(send_email, to=..., subject=...)
        return ctx.success_result(sent=True)
    except CircuitBreakerOpen:
        ctx.log_warning("Email service unavailable")
        raise
```

**Note:** Circuit breaker state is per-worker-process in multi-worker deployments.

---

## Architecture

```
app/core/background/
├── __init__.py          # Public API exports
├── celery_app.py        # Celery configuration & worker signals
├── tasks.py             # Core/system tasks
├── README.md            # <- You are here
├── internals/
│   ├── base.py          # BaseTask, DatabaseTask
│   ├── decorators.py    # @simple_task, @db_task
│   ├── context.py       # TaskContext (unified task interface)
│   ├── session.py       # Async DB session management
│   ├── event_loop.py    # Event loop handling for async in sync workers
│   ├── exceptions.py    # Retriable vs non-retriable errors
│   ├── retry.py         # Predefined retry policies
│   ├── monitoring.py    # TaskMetrics, Timer, StatsCounter
│   ├── logging.py       # TaskLogger
│   └── testing.py       # TaskTestContext, mock utilities
└── extras/
    └── circuit_breaker.py  # Optional circuit breaker pattern
```

---

## Checklist for New Tasks

- [ ] Create `tasks.py` in your module (if not exists)
- [ ] Import: `from app.core.background import simple_task, db_task, TaskContext`
- [ ] Choose decorator: `@simple_task` (no DB) or `@db_task` (with DB)
- [ ] Set unique `name` parameter
- [ ] Choose appropriate `retry_policy` and `queue`
- [ ] Use `ctx.log_*` for logging
- [ ] Use `ctx.validate_uuid()` for UUID parameters
- [ ] Use `ctx.not_found_error()` / `ctx.validation_error()` for failures
- [ ] Return `ctx.success_result(...)` on success
- [ ] Add to `__all__` for explicit exports
