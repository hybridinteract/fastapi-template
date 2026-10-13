# Deployment

> How the app gets onto a server.
> Last verified against the code: 13 October 2026.

Deploy with **[deployctl](https://github.com/hybridinteract/deployctl)** — its README is the full
documentation. This page says how it fits this app; it does not repeat the tool's docs.

> The bundled `deploy-v2/` bash scripts were removed in favour of deployctl. Do not reintroduce them.

## What it is

A CLI that deploys containerised apps to one server or a fleet over SSH, from your machine, GitHub
Actions, or a local web panel. The server needs only Docker, an SSH user and a writable directory;
images are built elsewhere and pulled from a registry. Releases are health-gated and roll back on
failure.

## Getting started

```bash
uv tool install git+https://github.com/hybridinteract/deployctl@v0.14.1   # pin a release tag
gh auth login && gh auth refresh -h github.com -s read:packages
deployctl access

deployctl init --mode single      # scaffolds deploy/ — or --mode cluster
# fill in deploy/config/*.env, then:
deployctl setup --env production && deployctl validate --env production
deployctl deploy doctor && deployctl deploy init
deployctl ssl setup               # single-host TLS
```

Day to day: `deploy update`, `deploy rollback`, `backup run|list|restore`, or `ci init` so merges
deploy themselves. Add `--dry-run` to any deploy command to print what it would run. Check the
deployctl README for the current version and the exact flags before relying on the lines above.

## The image

`docker/Dockerfile` is multi-stage — a `python:3.13-slim` builder, then a runtime that drops to a
non-root `appuser` (uid 1000). Healthcheck hits `/health`. The entrypoints are
`docker/docker-entrypoint.sh`, `celery-worker-entrypoint.sh` and `flower-entrypoint.sh`.

> The image is Python 3.13 while `pyproject.toml` sets `requires-python = ">=3.11"`. That is
> deliberate — the floor is what the code needs, the image is what we deploy — but it means a 3.11-only
> failure will not reproduce locally on 3.13, nor in CI, which also runs 3.13. Tracked in
> [`../planning/modernization.md`](../planning/modernization.md).

## Before a first production deploy

- [ ] `SECRET_KEY` and `JWT_SECRET_KEY` generated fresh — never carried over from `.env.example`.
- [ ] `ENVIRONMENT=production`, which turns on `TrustedHostMiddleware` — and `TRUSTED_HOSTS` set to
      the real domains. Its default is `["*"]`, which admits any `Host` header.
- [ ] `alembic upgrade head` applied, and the migration's `downgrade()` tested somewhere first —
      CI's integration job does both, plus `alembic check`, on every push.
- [ ] A `celery_worker` beside the API, or every dispatched task is silently dropped.
- [ ] CORS origins set to the real frontend origin, not `*`.
- [ ] `AUTH_PHONE_OTP_ENABLED` left `false` until a real SMS provider is implemented — `noop`, the
      only one, refuses in production rather than write codes to the log.
- [ ] `python -m app.iam.create_admin` run once, and its credentials stored somewhere real.
