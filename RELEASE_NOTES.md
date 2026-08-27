# Release Notes

All notable changes to this project template are tracked here.
Follow [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-03-05

### 🎉 Initial Template Release

This is the cleaned base template extracted from the salescrm_backend project.
It provides a production-ready starting point for any FastAPI + PostgreSQL + Redis backend.

#### Included Modules
- **`core/`** — Shared infrastructure: database, settings, CRUD base, exceptions, middleware, logging, metrics, Celery, Redis cache, object storage
- **`user/`** — Complete auth + RBAC: JWT (access + refresh tokens), role/permission management, user admin
- **`activity/`** — Append-only audit log (actor, action, resource, details, IP)
- **`release_notes/`** — "What's New" system with versioned, publishable release notes

#### Base Roles
- `super_admin` — Full access, bypasses all permission checks
- `admin` — User + system management
- `member` — Standard authenticated user

#### Infrastructure
- Async SQLAlchemy 2.0 + asyncpg
- Alembic async migrations (timestamped filenames)
- Celery + Redis (broker DB 0, result backend DB 1)
- Prometheus metrics via `/metrics`
- DigitalOcean Spaces / S3-compatible object storage
- Multi-stage Dockerfile (`python:3.13-slim`, non-root user)
- Docker Compose with health checks on all services

---

## [1.0.1] — 2026-05-03

### Changed

- **Conventions** — `docs/PROJECT_CONVENTIONS.md` updated with modern FastAPI patterns: `Annotated` type aliases, return-type annotations over `response_model=`, router-level config, async-vs-sync guidance, streaming (SSE / JSON Lines / bytes), and new hard rules (no Ellipsis defaults, no `RootModel`, no `ORJSONResponse`)
- **Dependency aliases** — `SessionDep`, `CurrentUserDep`, `SuperUserDep` exported from `core/database.py` and `user/auth_management/utils.py`; all route files migrated to use these aliases instead of inline `Depends()` calls
- **Return types** — `response_model=` removed from all route decorators; replaced with function return type annotations for Pydantic-side serialisation
- **Router config** — `prefix`, `tags`, and shared `dependencies` moved onto each `APIRouter` definition; `include_router()` calls in `apis/v1.py` are now config-free
- **`activity` module** — Added `dependencies.py` (`ActivityServiceDep`); router-level `require_permission("activity:read_all")` guard replaces per-endpoint `dependencies=`; removed inline service instantiation from routes
- **`release_notes` module** — Added `dependencies.py` (`ReleaseNoteServiceDep`); routes use `SuperUserDep` instead of manual `_require_superuser()` helper; `Field(...)` Ellipsis removed from `ReleaseNoteCreate` schema
- **Query params** — All `Query()` / `Path()` declarations migrated to `Annotated[T, Query(...)]` style across activity, release notes, and user management routes
- **`activity/schemas.py`** — Removed `Field(...)` Ellipsis from `BulkDeleteRequest.ids`

---

## [1.1.0] — 2026-08-27

### Security

- **`python-jose` → PyJWT** — python-jose is unmaintained with open advisories. Swapped to PyJWT (the library FastAPI's security tutorial uses). Installed as `pyjwt[crypto]` so RS256/ECDSA stay available, as `python-jose[cryptography]` provided. `except JWTError` → `except InvalidTokenError`, the base class of every PyJWT failure
- **`passlib` → pwdlib** — passlib is unmaintained and reads `bcrypt.__about__`, removed in bcrypt 5.x. New passwords hash with **Argon2id**; `BcryptHasher` is retained in the hasher chain so existing passlib hashes still verify. **No forced password reset, no DB migration** (`hashed_password` is `String(255)`; Argon2 needs 97)
- **Dropped the `bcrypt>=4.0.1,<5.0.0` pin** — it existed only to keep passlib working

### Changed

- **FastAPI floor `>=0.115.0` → `>=0.141.1`** — the old floor allowed installs where documented conventions were `ImportError`s (`Depends(scope=)` needs 0.121.0, `fastapi.sse` needs 0.135.0). Lockfile 0.135.1 → 0.141.1; verified `prometheus-fastapi-instrumentator` survives the 0.137.0 `router.routes` refactor
- **Ellipsis defaults removed** — 11 `Field(..., …)` → `Field(…)` in `core/settings.py`, `auth/schemas.py`, `user/schemas.py`, completing the cleanup started in 1.0.1

### Fixed

- **`datetime.utcnow()` → `utc_now()`** — 10 sites in `core/exceptions.py`. Deprecated since Python 3.12 (the image is `python:3.13-slim`) and returned naive datetimes, so error `timestamp` fields were unmarked UTC. They now carry `+00:00`, which fixes clients parsing them as *local* time

### Added

- **`verify_and_update_password()`** in `auth/tokens.py` — verifies and returns an upgraded Argon2 hash for credentials still on an older scheme. Not wired into login yet (opt-in)
- **`docs/MODERNIZATION.md`** — tracker for alignment with the official FastAPI agent skill: what changed, verification evidence, and the pending Tier 2/3 checklist

---

<!-- Template: copy this block when creating a new release -->
<!--
## [X.Y.Z] — YYYY-MM-DD

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 
-->
