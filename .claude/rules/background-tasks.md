---
paths:
  - "app/**/tasks.py"
  - "app/core/background/**"
---
# Background tasks (Celery)

> The long version: [`app/core/background/README.md`](../../app/core/background/README.md) ·
> [`docs/PROJECT_CONVENTIONS.md`](../../docs/PROJECT_CONVENTIONS.md) §12.
> Last verified against the code: 13 October 2026.

## The rules

1. **A module's tasks live in `app/<module>/tasks.py`.** Infrastructure — the app, decorators,
   context, retry, session handling — lives in `app/core/background/`. Never mix the two.
2. **Use `app/core/background/internals/session.py` for a DB session inside a task**, never the
   FastAPI `get_session` dependency. There is no request to scope to, and the request-scoped
   teardown will not run.
3. **A task takes JSON-serialisable arguments only** — ids and primitives, never an ORM object, a
   Pydantic model or a session. The object you pass is serialised to the broker; by the time the
   worker sees it, it is detached and its transaction is gone. Pass `str(user.id)`, re-fetch inside.
4. **A dispatch is not transactional.** `.delay()` fires whether or not the surrounding transaction
   commits — so dispatch **after** `commit()`, or a rollback leaves work queued for a change that
   never happened.
5. **Never await a fire-and-forget dispatch for its result** inside a request path. If the caller
   needs the answer, it is not a background task.
6. **A task must be idempotent.** It will be retried — on failure, on worker restart, and on broker
   redelivery. "Runs exactly once" is not something the broker offers.
7. **Never log a message body, a token, or a verification code.** Task arguments end up in the
   worker's log and in Flower.
8. **The Celery app path is `app.core.background.celery_app:celery_app`.** Entrypoints and the
   compose file reference it by that string; changing the module path breaks the worker silently.

## Where it IS used

| Where | What |
|---|---|
| [`app/core/background/celery_app.py`](../../app/core/background/celery_app.py) | The app, queues, and routing |
| [`app/core/background/internals/`](../../app/core/background/internals/) | Decorators, `TaskContext`, retry, event loop, session, monitoring, testing helpers |
| [`app/core/background/extras/circuit_breaker.py`](../../app/core/background/extras/) | Opt-in breaker for flaky external calls |
| [`app/activity/tasks.py`](../../app/activity/tasks.py) | `write_activity_log` — the reference task. Fire-and-forget, `low_priority` queue |

## Where it is deliberately NOT applied

- **`asyncio.run()` is allowed in `app/core/background/` and in CLI entrypoints** (`seed.py`,
  `create_admin.py`). The general rule is to bridge sync↔async with Asyncer, but those files *are*
  the event-loop lifecycle — there is no running loop to bridge into.
- **Nothing that must be transactional goes in a task.** If it has to happen with the write, it
  happens in the service, inside the same commit.

## Known gaps

- **A missing `celery_worker` is silent to the API.** It accepts the request, dispatches, and returns
  200; the work is simply never done. The worker container has its own healthcheck
  (`celery inspect ping` in `docker-compose.yml`), but that only reports on a worker that exists —
  nothing on the API side notices when none is running. When a task "does nothing", check
  `docker compose logs celery_worker` before anything else.
- Retry policy is per-task and not centrally asserted. Read `internals/retry.py` before choosing one.

## How to re-check this rule

```bash
# Every task in the repo, and every dispatch site. Module tasks use the house decorators
# @db_task / @simple_task (app/core/background/internals/decorators.py), not @celery_app.task.
grep -rn "@db_task(\|@simple_task(\|@shared_task\|@celery_app.task" app --include="*.py"
grep -rn "\.delay(\|\.apply_async(" app --include="*.py"

docker compose logs celery_worker --tail 50
```
