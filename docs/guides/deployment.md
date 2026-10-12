# Deployment

> How this template gets onto a server.
> Last verified against the code: 9 September 2026.

The deployment system lives in [`../../deploy-v2/`](../../deploy-v2/) and has its own documentation.
This page exists so you know it is there and which file to open.

| Document | Covers |
|---|---|
| [`deploy-v2/QUICK_START.md`](../../deploy-v2/QUICK_START.md) | **Start here.** Server bring-up step by step: DNS, SSL, first deploy, day-2 operations |
| [`deploy-v2/README.md`](../../deploy-v2/README.md) | The full system — Docker, nginx, SSL, backups, monitoring templates |
| [`deploy-v2/DOCS_AUTH.md`](../../deploy-v2/DOCS_AUTH.md) | Putting htpasswd basic-auth in front of `/docs` |

## What it is

Bash-driven, no orchestrator. `deploy-v2/scripts/` holds `setup.sh`, `deploy.sh`, `ssl.sh` and
`validate.sh`; `deploy-v2/templates/` holds the nginx, redis, prometheus, grafana and
staging/production compose files that those scripts render.

## The image

`docker/Dockerfile` is multi-stage — a `python:3.13-slim` builder, then a runtime that drops to a
non-root `appuser` (uid 1000). Healthcheck hits `/health`. The entrypoints are
`docker/docker-entrypoint.sh`, `celery-worker-entrypoint.sh` and `flower-entrypoint.sh`.

> The image is Python 3.13 while `pyproject.toml` sets `requires-python = ">=3.11"`. That is
> deliberate — the floor is what the code needs, the image is what we deploy — but it means a 3.11-only
> failure will not reproduce locally on 3.13. Tracked in
> [`../planning/modernization.md`](../planning/modernization.md).

## Before a first production deploy

- [ ] `SECRET_KEY` and `JWT_SECRET_KEY` generated fresh — never carried over from `.env.example`.
- [ ] `ENVIRONMENT=production`. Settings refuses to boot with `AUTH_EXPOSE_DEV_CODES=true` here.
- [ ] `alembic upgrade head` applied, and the migration's `downgrade()` tested somewhere first.
- [ ] A `celery_worker` beside the API, or every dispatched task is silently dropped.
- [ ] CORS origins set to the real frontend origin, not `*`.
- [ ] `python -m app.iam.create_admin` run once, and its credentials stored somewhere real.
