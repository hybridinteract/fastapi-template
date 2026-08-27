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

## [1.2.0] — 2026-08-27

Conventions alignment (Tier 2). Full detail in `docs/MODERNIZATION.md`.

### Added

- **Ruff + ty are actually installed** — §1 named them as the toolchain but neither was in `pyproject.toml` and nothing enabled the FastAPI ruleset it claimed. Added `[tool.ruff]` selecting `E, F, I, UP, B, ASYNC, FAST`. **`FAST` passes with zero findings** — the route/DI/router layers are idiomatic
- **HTTPX + Asyncer promoted to runtime dependencies** — conventions §1/§4/§19 mandate both; neither was installed, making those rules unenforceable
- **`PROJECT_CONVENTIONS.md` §21 "Deviations from the Official FastAPI Skill"** — records SQLModel, the FastAPI CLI, and `app.frontend()` as deliberate departures with reasons, plus a convention → minimum-FastAPI-version table
- **`verify_and_update_password()`** is documented as the credential-upgrade path

### Changed

- **§10 rewritten** — `params: XxxListParams = Depends()` was the class-dependency anti-pattern (the skill's literal "DO NOT DO THIS", contradicting our own §5). Now `Annotated[XxxListParams, Query()]`, which needs no `Depends` and renders flat query params in OpenAPI. `Literal[...]` replaces the `XxxSortField` Enum to match `core/schemas.py`
- **`ListParams` is now `frozen=True`** — §10 claimed "Pydantic models are immutable"; they weren't. Mutation now raises, and `model_copy(update={...})` is the documented scope-override idiom
- **§9 permission-guard example** rewritten with `Annotated` aliases, leading with the router-level guard the code actually uses
- **§19** — `utc_now()` replaces `datetime.now(timezone.utc)`, resolving the §6/§19 contradiction; the blanket asyncio ban is scoped to request paths, exempting Celery/CLI event-loop lifecycle (which legitimately violated it)
- **`get_session()` docstring** no longer teaches the inline `Depends()` anti-pattern inside the file that defines `SessionDep`

### Fixed

- **§5's `scope` example was broken code** — `def get_audit_writer(scope="function")` turns `scope` into a *query parameter*. It belongs on `Depends(fn, scope="function")`
- **§15** — removed a false `-> PNGStreamingResponse` return annotation from a generator
- **`decode_token` now raises `from None`** so the JWT failure reason can't leak into the traceback chain

### Notes

- **`E712` is disabled on purpose.** In SQLAlchemy `Model.col == False` is the correct SQL predicate; ruff's suggested `not Model.col` evaluates in Python and silently produces the wrong query — it would have broken 11 filters
- **502 cosmetic lint findings remain** (`Optional[X]`→`X | None`, `List[]`→`list[]`, import sort). Deliberately not swept — that belongs in its own reviewable commit
- 🐞 **`app/core/object_storage/storage.py` defines `StorageService` and `get_storage()` twice**, with differing behavior. Lines 30–423 are dead code; the live version starts at line 446. Found by the new lint config, **not fixed** — see `docs/MODERNIZATION.md`

---

## [1.3.0] — 2026-08-27

Dependency refresh — every package moved to its latest release. Detail in `docs/MODERNIZATION.md`.

### Fixed

- 🐞 **`greenlet` was never installed on Apple Silicon, breaking all async DB calls locally.** SQLAlchemy declares greenlet behind a platform marker listing `aarch64`/`x86_64`/`amd64`/`win32` — Apple Silicon macOS reports `arm64`, which matches none of them. Linux containers report `aarch64`, so **Docker always worked and only native macOS dev was broken**, failing on the first DB round-trip with *"the greenlet library is required to use this function"*. Fixed by declaring `sqlalchemy[asyncio]>=2.0.52`, whose extra requires greenlet unconditionally

### Changed

- **All 23 direct dependency floors raised to the latest published release.** Notable major jumps: **starlette 0.52.1 → 1.6.0** (permitted — FastAPI 0.141.1 declares `starlette>=0.46.0` unbounded), **redis 7.2.1 → 8.1.0**, **prometheus-fastapi-instrumentator 7.1.0 → 8.1.0**, **rich 14 → 15**, **cryptography 46 → 50**, gunicorn 25 → 26, uvicorn 0.41 → 0.52, typer 0.24 → 0.27
- **bcrypt is now unpinned and resolves to 5.0.0** — the release that breaks passlib. Only reachable because 1.1.0 migrated to pwdlib
- Point releases: sqlalchemy 2.0.52, pydantic 2.13.4, pydantic-settings 2.15.0, alembic 1.19.1, celery 5.6.3, asyncpg 0.31.0, boto3 1.43.81, pandas 3.0.5, pillow 12.3.0, flower 2.1.0, python-multipart 0.0.32, email-validator 2.3.0, pytest 9.1.1, pytest-asyncio 1.4.0, ruff 0.16.4, ty 0.0.75

### Notes

- `pydantic-core` stays at 2.46.4 (latest is 2.48.0) because pydantic 2.13.4 pins it exactly — correct, not stale
- Verified end-to-end after the bump: full middleware stack (CORS, GZip, TrustedHost, timing), 422/401 handlers, `/metrics`, `/docs`, and the complete auth suite. `ruff --select FAST` still clean; no `DeprecationWarning`s at boot; resolves for both Python 3.11 and 3.13
- Starlette 1.x deprecates `httpx` with `TestClient` in favour of `httpx2` — will matter when tests are written

---

## [1.4.0] — 2026-08-27

Defect fixes and the Tier 3 capability work. Detail in `docs/MODERNIZATION.md`.

### Fixed

- 🐞 **Every public file upload raised `AttributeError`.** `object_storage/storage.py` contained two different `StorageService` implementations concatenated (lines 30 and 446) plus two `get_storage()`. Python bound the last one — and *that* half's `_get_public_url()` referenced `settings.spaces_public_url`, which does not exist, so `upload(public=True)` always crashed. Consolidated to one class (833 → 417 lines) keeping the working `S3_PUBLIC_DOMAIN` URL builder and `hasattr`-guarded `seek()` from the dead half, and the settings-driven presigned-URL expiry from the live half
- 🐞 **Login leaked whether an email was registered.** An unknown email returned before any hashing (0.000 ms) while a known one paid a full Argon2 verification (37.72 ms) — a ~180,000x timing oracle. Login now always performs exactly one verification, against a dummy hash when the account is missing. Measured after: 1.00x
- 🐞 **Activity log pagination could repeat or drop rows.** The query ordered by `created_at DESC` with no tiebreaker, so logs sharing a timestamp were unstable across pages. Now `ORDER BY <sort>, id DESC` per §10
- **Google OAuth shipped unusable** — `google-auth` was in no dependency group, so enabling `AUTH_GOOGLE_OAUTH_ENABLED` registered routes that always failed with "Google auth library not installed". Added `[project.optional-dependencies] google = ["google-auth[requests]>=2.57.0"]`; install with `uv sync --extra google`

### Added

- **`.env.example`** — generated from `Settings` and `AuthConfig` so it cannot drift: required block first, then every optional field commented-out with its real default. Also covers `FLOWER_*`, which `docker-compose.yml` consumes but no settings class declares. Verified by booting the app from `.env` alone
- **Transparent password rehash on login** — `verify_and_update_password()` is now wired in, so a credential still on legacy bcrypt is rewritten as Argon2id on next sign-in. Rides the existing commit in `issue_tokens()`; no extra write
- **Sorting on the activity log endpoint** — `sort_by` (`created_at` / `action` / `actor_name`) and `sort_order`, rendered as typed dropdowns in OpenAPI
- **`PROJECT_CONVENTIONS.md` §5 "Annotated for request parameters"** — covers `Query`/`Path`/`Header`/`Cookie`/`Form`/`File`, not just `Depends`

### Changed

- **`app/activity/` is now the §10 reference implementation** — `ActivityListParams(ListParams)` bound with `Annotated[..., Query()]`, `get_list_filtered()` using the shared `paginated_select()` helper instead of a hand-rolled window count, and a route signature that drops from nine parameters to three. §10 now points at it
- **`alembic_models_import.py` added to ruff's per-file-ignores** — its 11 "unused" imports are its entire purpose (§8); removing them would silently break migration autogenerate

### Notes

- Adopting `ListParams` silently changed the activity endpoint's page size from 50 to 100. `ActivityListParams` re-declares `limit` to keep 50, and §10 now warns about this when subclassing
- `scope="function"` on `SessionDep` was **not** adopted — flipping a global default on reasoning alone is what should be measured first. The semantics are documented in §5 and `get_session()` so the option stays discoverable
- OAuth-only accounts still return `PasswordLoginUnavailableError`, distinguishing them by message even though timing is now equal. That message is a deliberate UX affordance, so changing it is a product decision

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
