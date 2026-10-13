# Local Environment

> Getting the stack running, and the facts about it that cost time to rediscover.
> Last verified against the code: 13 October 2026.

For a first run, follow the Quick Start in [`../../README.md`](../../README.md). This guide covers
what that does not: the host/container split, and the things that surprise people.

## The five services

`docker-compose.yml` defines five containers, all named `${APP_NAME:-myapp}_<service>`:

| Service | Image / build | Default port | Needed for |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `${POSTGRES_PORT:-5432}` | Everything |
| `redis` | `redis:7-alpine` | `${REDIS_PORT:-6379}` | Cache **and** the Celery broker |
| `api` | `docker/Dockerfile` | `${API_PORT:-8000}` | The app |
| `celery_worker` | same image | — | Any `app/<module>/tasks.py` work |
| `flower` | same image | `${FLOWER_PORT:-5555}` | Watching tasks |

All five have healthchecks. `docker compose up -d postgres redis` is enough to run the app on the
host, which is the usual loop.

## The host/container split

**Both reach the same database**, because `postgres` publishes its port. That is what makes the split
work:

| Runs on the **host** | Runs in the **container** |
|---|---|
| `uv run pytest` | `alembic upgrade head` |
| `uv run ruff check app` · `uv run ty check app` | `python -m app.iam.seed` |
| `python3 scripts/check_docs.py` | `python -m app.iam.create_admin` |

Migrations and management commands go through the container so they use the same interpreter and
environment the deployed app will. Tests, lint and doc checks are faster on the host and need neither.

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.iam.seed
```

## Facts worth knowing before you lose an hour to them

- **`sqlalchemy[asyncio]`, not `sqlalchemy`.** Plain `sqlalchemy`'s greenlet marker does not match
  Apple Silicon's `arm64`, so the extra is required. It works in Docker either way, which is exactly
  why this is confusing on an M-series Mac.

- **Seeding runs automatically at startup** via `lifespan` in `app/core/main.py`, and is idempotent.
  Running `python -m app.iam.seed` by hand is for when you have just added permissions and do not
  want to restart.

- **The seed never deletes and never re-grants.** A grant you revoked on the access-control screen
  stays revoked across restarts; only a role or permission new to the database gets catalogue
  grants. Rule 3 in [`../../.claude/rules/permissions.md`](../../.claude/rules/permissions.md).

- **`api` mounts `./app` read-only** (`./app:/app/app:ro`). Code changes are visible to the container
  immediately; anything that writes inside `app/` from within the container will fail.

- **Phone OTP in development.** With `AUTH_PHONE_OTP_ENABLED=true`, the default
  `OTP_SMS_PROVIDER=noop` writes each code to the app log as `[DEV OTP] phone=… otp=…`. It is the only
  provider implemented. With `ENVIRONMENT=production` it refuses to send (503) rather than log a
  code. Email sign-up sends no verification mail; there is no mail provider.

- **A task that never runs is usually a missing worker.** The API accepts the request and dispatches
  happily with no `celery_worker` beside it. Check `docker compose logs celery_worker`, not the API's
  log — the task's own logging lands in the worker.

- **`.env` is not optional.** `SECRET_KEY` and `JWT_SECRET_KEY` have no defaults, by design: the app
  fails fast rather than booting with a guessable secret.

## The commands you will actually type

```bash
uv run ruff check app && uv run ruff format app     # lint + format
uv run ty check app                                  # types (see the caveat below)
uv run pytest                                        # fast tier — no database
uv run pytest -m ""                                  # + integration; needs Postgres
python3 scripts/check_docs.py                        # links, stamps, rule frontmatter
uv run pre-commit install                            # once per clone — ruff on changed files
```

**`ty` is not yet a gate.** It reports a few dozen inherited diagnostics, mostly SQLAlchemy dynamic
attributes. CI runs it non-blocking. Do not bulk-fix them inside a feature change — the triage is
tracked in [`../planning/modernization.md`](../planning/modernization.md).
