# Modernization Tracker

Bringing the template in line with the **official FastAPI agent skill**
(`fastapi/.agents/skills/fastapi/SKILL.md`) and current library practice.

- **Reviewed against:** FastAPI skill + all 6 reference docs (`streaming`, `dependencies`,
  `responses`, `pydantic`, `path-operations`, `other-tools`), FastAPI release notes through
  **0.141.1**, and the FastAPI security tutorial (`tutorial/security/oauth2-jwt.md`).
- **Scope rule:** only things this template *actually uses* whose correct usage has changed.
  Features we deliberately skip are listed under [Not Adopted](#not-adopted).

| Tier | Theme | Status |
|------|-------|--------|
| 1 | Stale/broken usage — libraries and APIs we already depend on | ✅ **Done** (2026-08-27) |
| 2 | `PROJECT_CONVENTIONS.md` contradicts itself or the code | ✅ **Done** (2026-08-27) |
| 3 | Defect fixes + new capabilities | ✅ **Done** (2026-08-27) — see [Tier 3](#tier-3--completed-2026-08-27) |
| — | Dependency refresh — every package to its latest release | ✅ **Done** (2026-08-27) |

---

## Tier 1 — Completed 2026-08-27

### 1. `python-jose` → **PyJWT** 🔐

**Files:** `app/user/auth/tokens.py`, `pyproject.toml`

python-jose is effectively unmaintained (last meaningful release 2021, open advisories around
algorithm confusion). FastAPI's official security tutorial moved to PyJWT.

```diff
- from jose import JWTError, jwt
+ import jwt
+ from jwt.exceptions import InvalidTokenError
```

`InvalidTokenError` is the base class for **all** PyJWT failures, so the single `except` clause
is an exact replacement for `except JWTError`. Verified that each failure mode subclasses it:

| Failure | PyJWT exception | Subclass of `InvalidTokenError` |
|---|---|---|
| Expired token | `ExpiredSignatureError` | ✅ |
| Bad signature | `InvalidSignatureError` | ✅ |
| Malformed token | `DecodeError` | ✅ |
| Algorithm confusion | `InvalidAlgorithmError` | ✅ |

Installed as `pyjwt[crypto]` to preserve RS256/ECDSA support that `python-jose[cryptography]`
provided — `JWT_ALGORITHM` is env-configurable, so dropping it would have silently broken any
project using asymmetric signing.

**No API change:** `jwt.encode()` returns `str` and accepts a `datetime` for `exp`, same as jose.

### 2. `passlib` + pinned `bcrypt<5` → **pwdlib[argon2,bcrypt]** 🔐

**Files:** `app/user/auth/tokens.py`, `pyproject.toml`

passlib 1.7.4 (2020) is unmaintained and reads `bcrypt.__about__`, which **bcrypt 5.x removed**.
The old `bcrypt>=4.0.1,<5.0.0` pin existed solely to keep a dead library alive. FastAPI's docs
now use pwdlib with Argon2 as the recommended algorithm.

```diff
- pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
+ password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))
```

**Hasher order is the migration strategy.** The first hasher writes new hashes (Argon2id); every
hasher is tried on verify — so credentials created by the old passlib implementation keep working.

> ⚠️ **`BcryptHasher` is not optional.** An Argon2-only `PasswordHash` raises `UnknownHashError`
> on a legacy bcrypt hash, which would lock out every pre-existing user. This was verified
> explicitly, not assumed.

`verify_password()` keeps its exact signature and now returns `False` (instead of raising) on an
unparseable hash.

**New:** `verify_and_update_password(plain, hashed) -> tuple[bool, str | None]` returns a fresh
Argon2 hash when the stored one used an older scheme. It is **not wired into the login flow** —
see [Pending](#tier-3--new-capabilities-worth-adopting).

### 3. `datetime.utcnow()` → `utc_now()` — 10 call sites

**File:** `app/core/exceptions.py`

Deprecated since Python 3.12; the Dockerfile runs `python:3.13-slim`. It returned a **naive**
datetime, so every error-response `timestamp` was unmarked UTC. Now uses the existing
`app.core.utils.utc_now()` helper, per convention §6.

> 📢 **Client-visible change.** Error timestamps go from `2026-08-27T10:00:00.123456`
> to `2026-08-27T10:00:00.123456+00:00`. This **fixes** a latent frontend bug — JavaScript
> parses the naive form as *local* time, so error timestamps were previously wrong by the
> viewer's UTC offset.

### 4. Ellipsis defaults removed — 11 call sites

**Files:** `app/core/settings.py` (5), `app/user/auth/schemas.py` (4), `app/user/user/schemas.py` (2)

Required by the skill's `pydantic.md` and already banned by our own conventions §19.

```diff
- password: str = Field(..., min_length=8)
+ password: str = Field(min_length=8)
```

Fields stay required and constraints stay enforced — verified, not assumed.

### 5. FastAPI floor `>=0.115.0` → `>=0.141.1`

**File:** `pyproject.toml`

The old floor allowed installs where documented conventions were `ImportError`/`TypeError`:

| Convention already in our docs | Needs |
|---|---|
| `Depends(..., scope=...)` (§5) | **0.121.0** |
| JSON Lines / byte streaming via `yield` (§15) | **0.134.0** |
| `fastapi.sse` — `EventSourceResponse` (§15) | **0.135.0** |

Lockfile moved 0.135.1 → **0.141.1**.

> ✅ **0.137.0 breaking change cleared.** That release turned `router.routes` from a flat
> `APIRoute` list into a tree. Our code never iterates `.routes`, but
> `prometheus-fastapi-instrumentator` does — verified `/metrics` still registers on 0.141.1.

---

## Tier 2 — Completed 2026-08-27

Aligning `docs/PROJECT_CONVENTIONS.md` with the skill *and* with the code it describes.
Three fixes required code changes, not just prose.

### Code changes

| Change | File | Why |
|---|---|---|
| `ListParams` is now `frozen=True` | `app/core/schemas.py` | §10 asserted "Pydantic models are immutable" — they were **not**. Mutation now raises, so the rule is enforced instead of merely stated. `model_copy(update={...})` is the documented override idiom. Verified query binding and validation are unaffected. |
| `get_session()` docstring rewritten | `app/core/database.py` | It taught `session: AsyncSession = Depends(get_session)` — the inline anti-pattern §5 bans — inside the very file that defines `SessionDep`. Now also documents why the default `scope="request"` matters (lazy-loaded ORM attributes resolve during serialization). |
| `raise ... from None` on the JWT 401 | `app/user/auth/tokens.py` | Caught by the new `B904` rule. Prevents the JWT failure reason from leaking into the traceback chain. |

### Toolchain — §1 is now true, not aspirational

§1 named Ruff, ty, HTTPX and Asyncer as the stack; **none were installed**, and nothing
enabled the FastAPI ruleset §1 claimed. Added `ruff` + `ty` to the dev group, `httpx` +
`asyncer` to runtime deps, and a real `[tool.ruff]` config selecting
`E, F, I, UP, B, ASYNC, FAST`.

> ✅ **`FAST` (the FastAPI ruleset) passes with zero findings.** The route, DI, and router
> layers are genuinely idiomatic — the 1.0.1 standardization pass holds up under the
> upstream linter.

> ⚠️ **`E712` is disabled deliberately.** In SQLAlchemy, `Model.col == False` is the correct
> way to build a SQL predicate. Ruff suggests `not Model.col`, which evaluates in Python and
> silently produces the wrong query — applying that "fix" would have broken 11 filters across
> `user/crud.py`, `auth/crud.py`, and `release_notes/crud.py`.

The remaining **502 findings are cosmetic** (177 `Optional[X]`→`X | None`, 85 `List[]`→`list[]`,
62 import-sort, 26 `timezone.utc`→`UTC`). Deliberately **not** auto-fixed: a 414-file sweep is
its own reviewable change, and fixing 3 lines in touched files while 179 others keep the old
style would only create inconsistency. Tracked below.

### Documentation changes

| § | Fix |
|---|---|
| **1** | Records PyJWT and pwdlib as the mandated auth libraries; toolchain row now names the real config and the `E712` carve-out |
| **5** | **Fixed broken example** — `def get_audit_writer(scope="function")` made `scope` a *query parameter*. `scope` belongs on `Depends()`. Added the sub-dependency scope rule and the 0.121.0 floor |
| **5** | Class-dependency section now points parameter bundles at `Annotated[Model, Query()]` instead of a `Depends()` factory |
| **9** | Permission-guard example rewritten with `Annotated` aliases; leads with the router-level guard, which is what the code actually does |
| **10** | **Rewritten.** Drops `params: XxxListParams = Depends()` (the skill's literal "DO NOT DO THIS") for `Annotated[XxxListParams, Query()]`; `Literal[...]` replaces the `XxxSortField` Enum to match `core/schemas.py`; adds the `model_copy` override idiom; scoped with a note that simple lists should keep flat `Query()` params |
| **15** | Removed the false `-> PNGStreamingResponse` annotation from a generator |
| **19** | `utc_now()` replaces `datetime.now(timezone.utc)` (resolving the §6/§19 split); the absolute asyncio ban is scoped to request paths with a Celery/CLI exemption; added rules for query-param bundles, `scope` placement, and the banned auth libraries |
| **21** | **New — "Deviations from the Official FastAPI Skill".** Records SQLModel, the CLI, and `app.frontend()` as deliberate departures with reasons, plus a convention→minimum-FastAPI-version table |

Verified afterwards: `Annotated[LeadListParams, Query()]` binds correctly, enforces `Literal`
and `ge`/`le` constraints as 422s, and renders **flat query parameters** in OpenAPI (an enum
dropdown for `sort_by`) rather than a request body.


## Dependency Refresh — Completed 2026-08-27

Every direct dependency floor raised to the latest published release, and the lockfile
resolved forward (`uv lock --upgrade`). **Only `pydantic-core` remains behind** (2.46.4 vs
2.48.0) — pydantic pins it exactly, so that is correct, not stale.

### 🐞 Bug found: `greenlet` was missing on Apple Silicon

The most important outcome of this pass. SQLAlchemy declares greenlet with a **platform
marker**, not unconditionally:

```
greenlet>=1; platform_machine == "aarch64" or ... "x86_64" or "amd64" or "win32" ...
```

Apple Silicon macOS reports `platform_machine == "arm64"`, which is **not in that list**. So
`sqlalchemy>=2.0.0` (no extra) never installed greenlet on an M-series Mac — and every async
DB call failed with:

```
the greenlet library is required to use this function. No module named 'greenlet'
```

Linux ARM containers report `aarch64` and Linux x86 reports `x86_64`, both of which *are*
matched — which is why **Docker always worked and only native macOS development was broken.**
Caught by an end-to-end request test, not by app boot: importing the app succeeds, the failure
only appears on the first DB round-trip.

**Fix:** `sqlalchemy[asyncio]>=2.0.52`. The `asyncio` extra declares `greenlet>=1`
unconditionally, which is the documented way to use SQLAlchemy's async engine. greenlet 3.5.5
now installs on every platform.

### Major-version jumps taken

| Package | From | To | Note |
|---|---|---|---|
| **starlette** | 0.52.1 | **1.6.0** | 0.x → 1.x. Permitted because FastAPI 0.141.1 declares `starlette>=0.46.0` with no upper bound. Verified end-to-end. |
| **redis** | 7.2.1 | **8.1.0** | Client only; unrelated to the Redis server version in Compose. |
| **prometheus-fastapi-instrumentator** | 7.1.0 | **8.1.0** | The one package that iterates `app.routes` — re-verified against the 0.137 routes-tree refactor. |
| **rich** | 14.3.3 | **15.0.0** | CLI output for `create_admin.py` / `seed.py`. |
| **bcrypt** | 4.3.0 | **5.0.0** | Now unpinned. This is the release that breaks passlib — reachable only because Tier 1 migrated to pwdlib. |
| **cryptography** | 46.0.5 | **50.0.1** | Transitive via `pyjwt[crypto]`. |
| **gunicorn** | 25.1.0 | 26.2.0 | |
| **uvicorn** | 0.41.0 | 0.52.4 | |
| **typer** | 0.24.1 | 0.27.1 | |

Point releases also taken: sqlalchemy 2.0.52, pydantic 2.13.4, pydantic-settings 2.15.0,
alembic 1.19.1, celery 5.6.3, asyncpg 0.31.0, boto3 1.43.81, pandas 3.0.5, pillow 12.3.0,
flower 2.1.0, python-multipart 0.0.32, email-validator 2.3.0, pytest 9.1.1,
pytest-asyncio 1.4.0, ruff 0.16.4, ty 0.0.75.

### Verified after the refresh

Added an end-to-end request suite (the unit-level checks alone would not have caught the
greenlet bug):

```
PASS  /health through full middleware stack
PASS  custom @app.middleware('http') timing header present
PASS  CORS preflight -> 200
PASS  GZip ASGI middleware, content-encoding=gzip
PASS  422 validation handler
PASS  401 via JWT dependency
PASS  /metrics endpoint serves
PASS  /docs renders
```

Plus: the full Tier 1 auth suite still passes, `ruff --select FAST` is still clean, no
`DeprecationWarning`s at import or boot, and `pyproject.toml` resolves cleanly for **both**
Python 3.11 (the declared floor) and 3.13 (the Docker image).

> ℹ️ Starlette 1.x deprecates using `httpx` with `TestClient` in favour of `httpx2`. Harmless
> today, but it will need addressing when the test suite gets written (§18).


## Tier 3 — Completed 2026-08-27

Defects first, then the capability work.

### Defect 1 — `storage.py` was two modules in one file, and the live half was broken

The duplication (found by ruff `F811`) was hiding a real bug. Inspecting it properly
**inverted the expected fix**: the *live* half was the broken one.

- `StorageService` was defined at line 30 **and** 446; `get_storage()` at 415 **and** 826
- Python binds the last definition, so lines 30–423 never ran
- The live half's `_get_public_url()` referenced `settings.spaces_public_url`, **which does
  not exist** — confirmed at runtime:
  `AttributeError: 'Settings' object has no attribute 'spaces_public_url'`

So **every public file upload raised `AttributeError`**, because `upload(public=True)` calls
`_get_public_url()` to build its return value. The dead half used `S3_PUBLIC_DOMAIN` and
`DO_SPACES_ENDPOINT_URL`, both of which *do* exist.

The fix keeps one class, built from the live half (minimizing behavior change) with the two
things the dead half had right:

| | Dead half | Live half | Kept |
|---|---|---|---|
| `_get_public_url` | `S3_PUBLIC_DOMAIN` + endpoint fallback | **broken** `spaces_public_url` | **dead half** |
| `file.seek(0)` | `hasattr` guarded | unguarded | **dead half** |
| presigned expiry | hardcoded `3600` | `DOCUMENT_URL_EXPIRY_HOURS` | **live half** |

833 → 417 lines. Verified: CDN path returns `https://cdn.example.com/uploads/x.png`,
fallback returns `https://<endpoint>/<bucket>/<key>`.

### Defect 2 — Google OAuth shipped unusable

`google-auth` was in no dependency group, so enabling `AUTH_GOOGLE_OAUTH_ENABLED` registered
routes that always failed with *"Google auth library not installed"*.

Added `[project.optional-dependencies] google = ["google-auth[requests]>=2.57.0"]`.

> The `[requests]` extra is required — `google.auth.transport.requests` is the transport the
> provider imports, and google-auth does not pull it in by itself. This brings `requests` in
> as google-auth's *internal* transport; it does not relax the §19 rule that our own outbound
> HTTP goes through HTTPX.

Verified both ways: `uv sync --extra google` registers the provider and reaches real token
verification; a plain `uv sync` still boots the app with the provider absent.

### Defect 3 — no `.env.example`

Conventions §2 listed it and it did not exist, while `Settings` has **5 required fields with
no defaults** — so a fresh clone could not start without reading the source.

Generated from `Settings` and `AuthConfig` (211 lines), so it cannot drift from the code:
required block first, then every optional field commented-out with its real default, grouped
by the section headers in `settings.py`. Also covers `FLOWER_USERNAME` / `FLOWER_PASSWORD` /
`FLOWER_PORT`, which `docker-compose.yml` consumes but no settings class declares.

Verified by filling it in and booting the app from `.env` alone with no shell environment.

### Feature 1 — login hardened against account enumeration

`login()` returned early when the email was unknown, doing **zero** hashing work — while a
known email paid a full Argon2 verification. Measured gap:

| | Before | After |
|---|---|---|
| known email, wrong password | 37.72 ms | 38.20 ms |
| unknown email | **0.000 ms** | 38.39 ms |
| ratio | **~180,000x** | **1.00x** |

Login now always performs exactly one verification, against `DUMMY_PASSWORD_HASH` (a hash of
an unguessable per-process secret) when the account is missing or has no password.

> Not addressed: an OAuth-only account still returns `PasswordLoginUnavailableError`, which
> distinguishes it by *message*. That is a deliberate UX affordance, so changing it is a
> product decision rather than a fix.

### Feature 2 — transparent password rehash on login

`login()` now uses `verify_and_update_password()` and persists the upgraded hash, so a
credential still on legacy bcrypt is rewritten as Argon2id on the user's next sign-in. No
extra commit — it rides the existing one inside `issue_tokens()`.

Verified: bcrypt hash upgrades to `$argon2id$`, an existing Argon2 hash is left untouched,
and a wrong password is still rejected.

### Feature 3 — `app/activity/` is now the §10 reference implementation

`ListParams` had been `frozen=True` and fully documented since Tier 2 but was subclassed by
nothing. `activity` was the right module to adopt it: five filters and **no joins**, so no
row-duplication risk in a windowed count.

- `schemas.py` — `ActivityListParams(ListParams)` with `sort_by` as a `Literal`
- `crud.py` — `get_list_filtered(session, params)` via the shared `paginated_select()`
- `service.py` — `list_logs(session, params)`, a pass-through
- `routes.py` — `params: Annotated[ActivityListParams, Query()]`; the signature drops from
  nine parameters to three

Two real fixes came with it:

- **Added the missing pagination tiebreaker.** The old query ordered by `created_at DESC`
  with no secondary key, so logs sharing a timestamp could repeat or vanish across pages.
  Now `ORDER BY <sort>, id DESC`.
- **Preserved the end-of-day widening.** The route was expanding `date_to` to `time.max`
  before calling the service. That logic moved into `_build_filters`, next to the comparison
  it affects — dropping it would have made `date_to=2026-08-27` silently exclude that whole
  day. Verified in compiled SQL: `created_at <= '2026-08-27 23:59:59.999999+00:00'`.

> ⚠️ **Caught during review:** inheriting `ListParams` silently changed the endpoint's page
> size from 50 to 100. `ActivityListParams` re-declares `limit` to keep 50, and §10 now warns
> about this when subclassing.

Verified: OpenAPI exposes nine **flat query parameters** (not a request body), `sort_by`
renders as a typed dropdown, and `limit` keeps `min 1 / max 500 / default 50`.

### Also fixed

- `alembic_models_import.py` added to ruff's per-file-ignores. Its 11 "unused" imports are
  its entire purpose (§8) — removing them would silently break migration autogenerate. Same
  class of config bug as the `E712` carve-out.


## Verification

Ran against the real application, not in isolation:

```
PASS  argon2 hash/verify
PASS  legacy bcrypt still verifies (no lockout)
PASS  verify_and_update upgrades bcrypt -> argon2
PASS  malformed hash returns False (no crash)
PASS  JWT encode/decode
PASS  invalid tokens -> 401 (InvalidTokenError path)
PASS  refresh-token helpers
PASS  app boots, OpenAPI generates (27 paths)
PASS  prometheus instrumentator survived 0.137 routes refactor
PASS  Field() without ellipsis still required + constrained
```

Also confirmed:
- **`hashed_password` is `String(255)`**; Argon2id hashes are 97 chars (bcrypt was 60).
  **No database migration required.**
- pwdlib verifies legacy bcrypt hashes under **both** bcrypt 4.3.0 (lockfile) and
  **5.0.0** (what a Docker build resolves).
- `python-jose` and `passlib` no longer appear anywhere in `uv.lock`.

---

## Migrating an existing project built on this template

1. `uv sync` — `python-jose`/`passlib` are removed, `pyjwt`/`pwdlib` added.
2. **No migration, no forced password reset.** Existing bcrypt hashes verify as-is; new and
   changed passwords are written as Argon2id.
3. Existing JWTs stay valid — same algorithm, same secret, same claims.
4. If you parse error-response `timestamp` fields, note the added `+00:00` offset (§3 above).
5. If you set `JWT_ALGORITHM` to an RS/ES algorithm, `pyjwt[crypto]` already covers it.

---

## 🐞 Live defect found by the new lint config — FIXED

Ruff's `F811` surfaced that `app/core/object_storage/storage.py` contained two different
implementations of the same module. Investigating it revealed the *live* half was the broken
one — `_get_public_url()` referenced a setting that does not exist, so every public upload
raised `AttributeError`.

Full write-up and the fix in [Tier 3, Defect 1](#defect-1--storagepy-was-two-modules-in-one-file-and-the-live-half-was-broken).

This is the concrete payoff of the Tier 2 toolchain work: the lint config paid for itself by
exposing a production bug that had been invisible.

---

## ⚠️ Unrelated issue found while verifying

**The Dockerfile ignores `uv.lock`.** `docker/Dockerfile` runs:

```dockerfile
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml
```

This resolves dependencies fresh at build time, so **Docker and local dev can install different
versions** — confirmed: local resolves `bcrypt 4.3.0`, the Docker path resolves `bcrypt 5.0.0`.

Under the old passlib code that divergence was a live hazard: bcrypt 5.0.0 breaks passlib, and
only the `<5` pin prevented it. That specific risk is gone, but the reproducibility gap remains.

Suggested fix (**not applied** — outside this scope):

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
```

---

## Pending

Everything from the original Tier 3 list is done except the items below. Completed work is
recorded in [Tier 3](#tier-3--completed-2026-08-27).

### Hygiene

- [ ] **Apply the cosmetic ruff findings** as one isolated commit — `uv run ruff check app --fix`
      handles most of them (`Optional[X]`→`X | None`, `List[]`→`list[]`, import sort); the rest
      need review. Do it alone so the diff stays reviewable.
- [ ] **Triage the `ty` baseline** (see below) before it can gate anything.
- [ ] **Wire `ruff` + `ty` into CI** — only after the two above, or CI starts red on day one.
- [ ] **Zero test files** despite pytest being configured (`testpaths = ["app"]`) and §18's
      checklist ending in "Write tests". Note that Starlette 1.x deprecates `httpx` with
      `TestClient` in favour of `httpx2` — decide that when the suite is written.

### Deliberately deferred

- [ ] **`scope="function"` on `SessionDep`** — would release the Postgres connection to the
      pool *before* the response is written to the network. Response data is serialized first,
      so lazy-loaded ORM attributes still resolve, and this template uses **zero** FastAPI
      `BackgroundTasks` (Celery instead), which is the main incompatibility. **Not flipped:**
      changing a global default on reasoning alone is exactly what should be measured first.
      The semantics are documented in §5 and in `get_session()`'s docstring so the option is
      discoverable.
- [ ] **OAuth-only accounts still return `PasswordLoginUnavailableError`**, which distinguishes
      them from unknown emails by *message* even though timing is now equal. That message is a
      deliberate UX affordance ("sign in with Google instead"), so removing it is a product
      decision, not a security fix.

### Worth deciding separately

- [ ] **`pandas` is a core dependency**, commented "optional — remove if not needed". pandas 3.x
      is a heavy install most projects won't use — move it and `openpyxl` to an optional extra
      alongside the new `google` one.
- [ ] **`requires-python = ">=3.11"` but Docker runs `python:3.13-slim`.** Raise the floor to
      3.12+. Resolution is verified for both today, so this is a tidying decision, not a fix.

### Not adopted

| Skill feature | Why not |
|---|---|
| `fastapi dev` / `fastapi run` + `[tool.fastapi]` entrypoint | Deployment is Docker Compose; uvicorn CMD stays |
| `app.frontend()` / `router.frontend()` | Frontend is Next.js SSR, deployed separately. Only serves built static assets |
| SQLModel over SQLAlchemy | Deliberate deviation — see §21 of the conventions |

### `ty` baseline

`uv run ty check app` reports **79 diagnostics**. Not triaged — the bulk (25
`unresolved-attribute`, 20 `unknown-argument`) are the usual SQLAlchemy dynamic-attribute
false positives, and the `unresolved-import` hits are the *deliberately optional* sentry and
google-auth integrations, both guarded by `try/except ImportError`. Needs a triage pass and a
suppression baseline before it goes into CI.
