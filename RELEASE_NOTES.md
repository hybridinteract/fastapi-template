# Release Notes

All notable changes to this project template are tracked here.
Follow [Semantic Versioning](https://semver.org/).

---

## [2.3.1] — 2026-10-13

Found by re-verifying every doc against the code. Five places where the code did not do what the
docs promised were fixed in code; two that need a product decision are recorded, not changed.

### Security
- **`developer_admin` could be granted through the API.** `POST /users/{user_id}/roles` assigned any
  role id, so a superuser could mint new total-bypass accounts over HTTP, which `CLAUDE.md` §5 forbids.
  `assign_roles` now refuses it with `RoleNotGrantableError` (403), and checks every role before
  writing any, so a refused request changes nothing.
- **An `inactive` user could still sign in.** `PATCH /users/{id}` with `{"status": "inactive"}`
  leaves `is_active` true, and the gates refused only `suspended` and `pending_verification`. Every
  status but `active` is now refused at sign-in, on every request, and on token refresh.
- **The `noop` SMS provider logged OTP codes in production.** It is the default and the only one
  implemented; with phone OTP on, anyone reading the logs could sign in as any phone user. In
  production it now refuses with `SmsProviderNotConfiguredError` (503).

### Fixed
- 🐞 **A revoked permission came back at the next restart.** The seed runs in `lifespan` and
  inserted every missing catalogue grant for every role, so revoking one on the access-control
  screen lasted only until the app restarted. It now seeds a grant only when its role or its
  permission is new to the database (`CLAUDE.md` §5); new roles and new permissions are still
  granted as before.
- 🐞 **`ILIKE` search input was never escaped**, so `50%` matched `500 off`, `a_b` matched `axb`, and
  a search containing a backslash could not match itself (verified on Postgres 16). New
  `escape_like()` in `app.core.utils`, used by the activity `actor_name` filter and the user search.
  The search docs already told you to import it — from a module that never existed.

### Changed
- `require_permission` denies with named `MissingPermissionError` / `AccessDeniedError` instead of a
  raw `HTTPException`; status, message and headers are byte-identical.
- `get_session`'s docstring example showed a route calling CRUD and committing — the pattern
  `CLAUDE.md` §2 forbids. It now shows route → service.

### Docs
- All 19 stamped docs re-verified against the code, and their errors fixed in place — among them a
  seed that "defines all roles" (the catalogue does), a `user/seed.py` and `get_current_active_user`
  that do not exist, an `AUTH_EXPOSE_DEV_CODES` setting that does not exist, a "no worker
  healthcheck" gap that was closed, and a task-listing grep that missed `@db_task`.
- **Recorded in `.claude/rules/permissions.md` → Known gaps, not changed:** 18 admin routes gate on
  `SuperUserDep` rather than a permission, so 17 of 18 catalogue permissions gate nothing; and no
  auth route has a throttle.

### Upgrade
Behaviour changes to check against your clients: users with `status = "inactive"` are now locked
out; assigning `developer_admin` through the API returns 403; phone OTP with `OTP_SMS_PROVIDER=noop`
returns 503 in production; `%` / `_` in search input now match literally; and the seed no longer
re-grants revoked permissions — a grant the old seed restored after you revoked it must be revoked
once more, and a new catalogue grant between an existing role and an existing permission needs a
data migration.

## [2.3.0] — 2026-10-12

Dependency refresh with security fixes, plus three pre-existing defects found while verifying it.
**Has a migration** (`43b28eb98417`). Detail and evidence: `docs/planning/modernization.md`,
"Dependency Refresh 2".

### Security
- **PyJWT 2.13.0 → 2.15.1** — 2.13.0 carried 14 advisories (1 critical, 5 high, 8 moderate). One reached this
  code: GHSA-8wjv-2p76-3863, a nested token header that made `jwt.decode()` raise `RecursionError`
  straight past `decode_token()` — a 500 any caller could trigger. Now a `DecodeError` → 401.
  The floor is commented as a security floor.
- **tornado 6.5.10, urllib3 2.8.0, mako 1.4.3** (via flower, boto3, alembic) — 7 more advisories.
  They are transitive, so their floors are `[tool.uv] constraint-dependencies` in `pyproject.toml`.
- OSV now reports **0 advisories across all 106 locked packages** (was 21 across 4).

### Fixed
- 🐞 **Missing migration for `oauth_accounts` and `phone_otps`, and for `users.email` /
  `users.hashed_password` becoming nullable.** The models arrived on 8 June 2026 (`aafdcc0`) without one, so every
  database built from migrations lacked both tables and **`GET /users/me` failed** (it lists linked
  OAuth accounts). New migration `43b28eb98417`; its `downgrade()` refuses, with the reason, while
  any OAuth- or phone-only user exists, instead of failing on a bare constraint error.
- 🐞 **`downgrade()` left the `userstatus` and `changetype` enum types behind**, so upgrade →
  downgrade → upgrade died with `type "userstatus" already exists` — the sequence CI's integration
  job runs. Both downgrades now drop their type.
- 🐞 **`GET /activity?action=…` never matched a row.** On Python 3.11+, `str()` of a `(str, Enum)`
  member is `"ActivityAction.CREATE"`, which the filter upper-cased and compared. All three enums
  (`ActivityAction`, `UserStatus`, `ChangeType`) are now `StrEnum`; stored values, Pydantic and
  OpenAPI are unchanged. First behaviour test: `app/activity/tests/test_list_filters.py`.

### Changed
- **FastAPI 0.141.1 → 0.143.0**, Starlette 1.6.0 → 1.7.0, Pydantic 2.13.4 → 2.14.1, uvicorn 0.54.0,
  asyncpg 0.32.0, Alembic 1.20.0, SQLAlchemy 2.0.52 → **2.0.54** (fixes an asyncio connection leak),
  and patch releases across the tree — 42 versions moved in all.
- **New transitive dependency: `opentelemetry-api`**, required by FastAPI since 0.142.0. Inert here:
  exporters start only with `FASTAPI_OTEL_AUTO_CONFIGURE=true`.
- **SQLAlchemy is capped `<2.1`** — a maturity call, not a code one; see `docs/DECISIONS.md`.
- `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT` (RFC 9110; the old name warns).
- `PermissionChecker` takes `CurrentUserDep` / `SessionDep` instead of bare `Depends()` — same
  sub-dependencies, now in the house style. New **`CacheDep`** alias in `app.core.cache`; its
  docstrings, README and examples use it.
- `ReleaseNote.author` is typed `Mapped["User | None"]`; the mapping is unchanged.
- **CI:** `actions/checkout` v4 → v7.0.1 and `astral-sh/setup-uv` v5 → v10.3.0, pinned by commit SHA
  (setup-uv no longer publishes `@v10`); `uv sync --locked`; the integration job runs
  `alembic check`, so a model with no migration now fails CI.
- **Tooling:** ruff 0.17.0 and ty 0.0.86, with the pre-commit `rev:`s moved to match
  (pre-commit-hooks v6.0.0). The `ruff-format` hook stays scoped to code: v0.17.0 added Markdown to
  its types, which would reformat doc snippets on every doc edit. CI now runs on Python 3.13, the
  Docker image's, via setup-uv's `python-version` (`.python-version` is gitignored by design).

### Upgrade
Run `alembic upgrade head` for `43b28eb98417`. If you created `oauth_accounts` or `phone_otps` by
hand, check the migration against your schema first. Any code doing `str(member)` on these enums
now gets the value, not `Cls.MEMBER`.

## [2.2.0] — 2026-09-10

Documentation and skills only — **no `app/` behaviour changed**, and `app/iam` was not touched.

### Changed
- **A module's shape is now chosen, not grown.** A domain module lays each layer out as a folder —
  `models/`, `schemas/`, `crud/`, `services/`, `routes/` — **from its first commit**. This reverses
  2.1.0's *"a file becomes a folder when it outgrows itself"*. That rule implies a threshold around
  600 lines; the largest file in this repo is 354, so it never fired and the decision was being made
  by accident. Reasoning and the tiebreaker: `docs/DECISIONS.md`, 10 September 2026.
- **Four named shapes, with a three-question decision procedure**: **flat**, **layered** (the
  default), **composite** (sub-modules with a declared import rank), **shared kernel** (business
  primitives, no HTTP surface, no tables). `docs/MODULE_CONVENTIONS.md` §6 holds the contracts;
  `CLAUDE.md` §1 holds the procedure. The shape and the step that chose it go in the module's
  `how-it-works.md`.
- **`app/core/tests/test_module_anatomy.py` is shape-aware.** It reads the shape from the layout and
  applies that shape's contract — a shared kernel has no `dependencies.py`, a composite may carry
  `exceptions.py` per sub-module — and additionally checks that a composite keeps **one**
  `dependencies.py`, `tests/` and `<module>_doc/` at its root. Two new tests; suite is 14, was 12.
- **`XListParams` moves from `schemas.py` to a flat `list_params.py`** in new modules, so `schemas/`
  can stay strictly one sibling per entity. `app/activity` predates this and is unchanged.
- **`/new-module` now decides the shape first** and branches four ways. It carries a
  `test_module_boundary.py` template, parameterised by the rank list, that resolves relative imports
  by counting dots and includes a `dependencies.py` constructor-injection check — the one place a
  rank can invert with no sub-module file importing upward.
- **`/review-module` gains a shape section**, checked before anything else.
- `docs/PROJECT_CONVENTIONS.md` §2 and §4 document layer packages and the per-`__init__.py`
  contracts; §10 documents `list_params.py`.

### Added
- `models/__init__.py` must re-export **every** model — `alembic_models_import.py` imports the
  package, so an omission is the same silent failure as an unregistered model, one level down.
  Recorded in `.claude/rules/models-and-migrations.md`, along with the `TYPE_CHECKING` rule for
  cross-sibling relationships.
- `crud/__init__.py` re-exports each class **and** its singleton; `routes/__init__.py` builds no
  aggregator.
- `app/core/tests/conventions.py` gains `module_shape()` and `sub_modules()`.

### Known
- **`app/iam` is a composite module with no rank and no boundary test, and its boundary has already
  dissolved** — `auth/` imports `user/` in 8 places, `user/services.py` imports `auth/` in 4, held
  together by one function-local import at `app/iam/auth/current_user.py:44`. Documented in
  `docs/MODULE_CONVENTIONS.md` §6.2 as the cautionary tale; **not fixed here**. Adding the boundary
  test before fixing the cycle would ship a test that starts red.
- **The template still contains no layered module** — every module here predates the rule and is
  genuinely small. `/new-module` generates the shape; the docs say so rather than hiding it.

## [2.1.0] — 2026-09-09

### Added
- **`CLAUDE.md`** — a 172-line guardrail, loaded in full by AI coding agents at the start of
  every session. Capped at 200 lines and enforced by `scripts/check_docs.py`.
- **`.claude/rules/`** — six path-scoped rule files (layering, routes/DI,
  models/migrations, permissions, background tasks, tests). Each declares `paths:` in
  frontmatter and is loaded automatically only when a file it governs is opened, so deep
  rules cost no context on unrelated work.
- **`.claude/skills/`** — `/new-module`, `/new-migration`, `/review-module`.
- **`.claude/settings.json`** and a `PostToolUse` hook that runs `ruff` on the file an agent
  just edited. Personal settings stay in the now-gitignored `settings.local.json`.
- **Tests, for the first time.** `app/conftest.py` (supplies the env the app needs at import
  time) plus four convention tests that enforce rules which otherwise fail silently:
  Alembic model registration, the layering contract, module anatomy, and router
  registration order. 12 tests, ~1s, no database.
- **`scripts/check_docs.py`** — dead relative links, `Last verified against the code:`
  stamps, `paths:` frontmatter on every rule, and the `CLAUDE.md` line budget.
- **CI** (`.github/workflows/ci.yml`) and **pre-commit**. CI gates on tests and docs; lint
  and types are reported non-blocking until the inherited baseline is triaged. `pre-commit` is a
  dev dependency — run `uv run pre-commit install` once per clone.
- `docs/MODULE_CONVENTIONS.md` (where code goes), `docs/WRITING_DOCS.md` (the
  doc-ownership contract), `docs/DECISIONS.md` (append-only), `docs/README.md` (the map),
  and `docs/guides/`.
- `app/activity/exceptions.py`, `app/release_notes/exceptions.py`, and module notes at
  `app/activity/activity_doc/` and `app/release_notes/release_notes_doc/`.
- A single pytest marker, `integration`, with `addopts = "--strict-markers -m 'not integration'"`.

### Changed
- **`app/apis/v1.py`: `rbac_router` now registers before `admin_router`.** Both live under
  `/users`, and FastAPI matches in registration order — with `admin_router` first, adding a
  `GET /users/{user_id}/roles` would have silently made `GET /users/meta/roles`
  unreachable. Verified against FastAPI 0.141.1 and covered by
  `app/apis/tests/test_route_registration.py`.
- **Services no longer raise raw `HTTPException`.** Nine call sites across
  `app/iam/user/services.py`, `app/iam/permission/services.py` and
  `app/release_notes/service.py` now raise named exceptions. New:
  `PhoneAlreadyInUseError`, `CannotDeleteSelfError`, `UserNotDeletedError`,
  `RoleNotFoundError`, `ProtectedRoleError`, `ReleaseNoteNotFoundError`,
  `ReleaseNoteVersionExistsError`. **Status codes and response bodies are unchanged.**
- `docs/PROJECT_CONVENTIONS.md` is backend-only; the Next.js sections moved to
  `docs/FRONTEND_CONVENTIONS.md`. Section numbers §1–§21 are unchanged — §16 is kept as a
  pointer so nothing downstream that cites a section number breaks.
- `docs/MODERNIZATION.md` → `docs/planning/modernization.md`;
  `docs/research_and_development/ai/AI_AGENT_INTEGRATION_DISCUSSION.md` →
  `docs/research/ai-agent-integration.md`.
- `README.md` trimmed from 365 to 250 lines — the duplicated conventions section was
  already drifting from `PROJECT_CONVENTIONS.md` and is now a table of links.

### Removed
- `fcube.py` — a stub that could only ever print "FCube CLI not found". Superseded by the
  `/new-module` skill. See `docs/DECISIONS.md`.
- `.agents/skills/` — an empty directory that was never populated.

### Upgrade
No API changes and no migration. For an existing project built on this template:
copy `CLAUDE.md`, `.claude/`, `scripts/check_docs.py` and `app/core/tests/`, then run
`uv run pytest` — the four convention tests will tell you where your project has drifted.

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

## [2.0.0] — 2026-09-09

The `user` module becomes `iam`. Breaking for every project built on the template:
import paths change, and the bypass role is renamed. No schema migration —
see Notes.

### Changed

- **`app/user/` → `app/iam/`** — "IAM" (identity and access management) names what
  the module actually does. It holds authentication, user accounts *and* RBAC;
  `user` named only one of the three. Adopted from the naming already in use in
  the most advanced downstream project, so work flows between them without a
  translation step
- **`permission_management/` → `permission/`** and **`permissions.py` →
  `permission_catalog.py`** — the catalogue is a list of constants, not the guards;
  the old names had this backwards
- 💥 **`super_admin` role renamed to `developer_admin`.** `SUPER_ADMIN_ROLE` →
  `DEVELOPER_ADMIN_ROLE`, and it is now defined **once** in `iam/config.py` with
  `permission/utils.py` and `create_admin.py` deriving from it — previously the
  same string was hardcoded in all three
- **Illustrative docstrings corrected** — `app/core/background/*` and
  `app/core/cache/examples.py` cited `app.user.tasks` / `app/user/services.py`,
  paths that never existed. They now point at real modules or clearly hypothetical ones

### Added

- **`app/iam/iam_doc/how-it-works.md`** — one-page tour of the module: the tables,
  the providers, tokens, the role model, and how the seed's three passes work
- **Migration `3c6589de23bb`** — data-only, renames the seeded role

### Upgrade

1. `from app.user import X` → `from app.iam import X`;
   `app.user.permission_management` → `app.iam.permission`;
   `app.user.permissions` → `app.iam.permission_catalog`
2. **Run `alembic upgrade head` before starting the app.** This is not optional
   if you have existing data — see Notes
3. `SUPER_ADMIN_ROLE` → `DEVELOPER_ADMIN_ROLE` in `.env` if you overrode it
4. Check for **relative** imports of the module — `from ..user.seed import run_seed`
   in `app/core/main.py` was one, and a search for `app.user` will not find it

### Notes

- **The module rename needs no schema migration.** All nine table names are
  unchanged (`users`, `roles`, `permissions`, `role_permissions`, `user_roles`,
  `refresh_tokens`, `oauth_accounts`, `phone_otps`), verified by diffing the
  SQLAlchemy metadata before and after — 127 lines of table, column, index and
  constraint definitions, identical
- **The role rename does need one.** `seed.py` is additive: it creates roles it
  cannot find and never renames. Without migration `3c6589de23bb`, an upgraded
  project gets a fresh `developer_admin` row beside the old `super_admin` one
  while existing admins stay on `super_admin` — silently losing their bypass,
  with nothing failing loudly. The migration handles all three states: rename in
  place, merge when both exist, no-op on a fresh database
- **Symbol names deliberately unchanged** — `SuperUserDep`, `is_super_admin()` and
  `create_super_admin()` keep their names, matching the downstream module this
  rename came from. Only the role string and the `*_ROLE` constant changed
- Route surface is byte-identical: the same 32 paths before and after

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
