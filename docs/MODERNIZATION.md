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
| 2 | `PROJECT_CONVENTIONS.md` contradicts itself or the code | ⬜ Pending |
| 3 | New capabilities worth adopting | ⬜ Pending |

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

### Tier 2 — `PROJECT_CONVENTIONS.md` fixes

- [ ] **§5 `scope` example is broken code** — `def get_audit_writer(scope="function")` makes
      `scope` a **query parameter**. It belongs on `Depends()`:
      `Annotated[AuditWriter, Depends(get_audit_writer, scope="function")]`
- [ ] **§10 mandates the class-dependency anti-pattern** — `params: XxxListParams = Depends()`
      is verbatim the skill's "DO NOT DO THIS", and contradicts our own §5.
      Use `params: Annotated[LeadListParams, Query()]` instead.
- [ ] **§10 prescribes Enums; `core/schemas.py` uses `Literal`** — the code is right, update the doc.
- [ ] **§10 `ListParams` is subclassed by nothing** — every list endpoint uses flat `Query()` params.
- [ ] **§9 permission-guard example uses inline `Depends()` defaults** — violates §5 and §19.
- [ ] **§19 vs §6 disagree on UTC** — standardize on `utc_now()`.
- [ ] **§15 byte-stream example has a false return annotation** on a generator.
- [ ] **§1 lists Ruff / ty / HTTPX / Asyncer — none are installed**, and no `[tool.ruff]` exists
      despite §1 claiming "FastAPI rules enabled" (the `FAST` ruleset).
- [ ] **§19 "never raw asyncio" is already violated** in `database.py`, `celery_app.py`,
      `seed.py`, `create_admin.py` — legitimately. Scope the rule to request-path sync↔async
      bridging; exempt Celery/CLI event-loop plumbing.
- [ ] **`get_session()` docstring** (`core/database.py:61`) teaches the old inline `Depends()`
      style inside the file that defines `SessionDep`.
- [ ] Add a **"Deviations from the official FastAPI skill"** section: the skill says *"prefer
      SQLModel over SQLAlchemy"* — we deliberately don't. `CRUDBase` generics, Alembic
      autogenerate, the RBAC join tables and `paginated_select` are all SQLAlchemy Core.
      Record it, or the next agent will "helpfully" migrate us.

### Tier 3 — New capabilities worth adopting

- [ ] **`scope="function"` on `SessionDep`** — releases the Postgres connection to the pool
      *before* the response is written to the network. Response data is serialized first, so
      lazy-loaded ORM attributes still resolve. Safe here specifically: this template uses
      **zero** FastAPI `BackgroundTasks` (Celery instead), which is the main incompatibility.
      Measure before flipping the default.
- [ ] **Wire `verify_and_update_password()` into the login flow** for transparent Argon2
      upgrades on sign-in. Adds a DB write to the login path — deliberate opt-in.
- [ ] **Timing-attack hardening** — the FastAPI reference implementation verifies against a
      dummy hash when the user doesn't exist, so response time doesn't reveal whether an email
      is registered. `email_password.py` currently returns early on unknown email.
- [ ] **Document `Annotated` for `Query`/`Path`/`Header`/`Form`/`File`** in §5, not just
      `Depends`. The code already does this correctly everywhere; the doc just never says it.

### Not adopted

| Skill feature | Why not |
|---|---|
| `fastapi dev` / `fastapi run` + `[tool.fastapi]` entrypoint | Deployment is Docker Compose; uvicorn CMD stays |
| `app.frontend()` / `router.frontend()` | Frontend is Next.js SSR, deployed separately. Only serves built static assets |
| SQLModel over SQLAlchemy | Deliberate deviation — see Tier 2 |

### Worth deciding separately

- [ ] **`pandas>=3.0.0` is a core dependency**, commented "optional — remove if not needed".
      pandas 3.0 was a major release (copy-on-write, string dtype). Heavy install for a template
      most projects won't use — move it and `openpyxl` to an optional extra.
- [ ] **`requires-python = ">=3.11"` but Docker runs `python:3.13-slim`.** Raise the floor to
      3.12+. There are 179 `Optional[...]` and 74 `List[`/`Dict[` that could modernize — cosmetic.
- [ ] **No `.env.example`** despite conventions §2 listing it.
- [ ] **Zero test files** despite pytest being configured (`testpaths = ["app"]`) and §18's
      checklist ending in "Write tests".
