# Project Conventions

> Authoritative guide for building and scaling modules in this FastAPI + Next.js stack.
> Applies to AI coding assistants and human developers equally — these are hard constraints.

---

## Reference Resources

| Resource | URL | Purpose |
|----------|-----|---------|
| Backend Template | https://github.com/hybridinteract/fastapi-template | Production-ready starter — clone this, never rebuild from scratch |
| Project Structure Standards | https://engineering.hybridinteractive.in/standards/project-structure/ | Canonical modular monolith + DDD guide |
| Official FastAPI Skill | https://github.com/fastapi/fastapi/blob/master/fastapi/.agents/skills/fastapi/SKILL.md | Upstream FastAPI conventions these rules are checked against — see §21 |
| Modernization Tracker | `docs/MODERNIZATION.md` | What has been aligned with the skill, and what is still pending |

---

## 1. Tech Stack

### Backend
| Concern | Technology |
|---------|-----------|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL via asyncpg |
| Migrations | Alembic (async) |
| Validation | Pydantic v2 |
| Auth | JWT (access + refresh) + RBAC |
| JWT library | PyJWT (`pyjwt[crypto]`) — never `python-jose` (unmaintained) |
| Password hashing | pwdlib — Argon2id for new hashes, bcrypt kept for verifying legacy ones. Never `passlib` (unmaintained) |
| Caching | Redis |
| Background Tasks | Celery + Flower |
| Config | Pydantic Settings (env-based) |
| Storage | S3-compatible (boto3) |
| Monitoring | Prometheus |
| Package Manager | uv |
| Linting / Formatting | Ruff — config in `pyproject.toml`, `FAST` (FastAPI) ruleset enabled |
| Type Checking | ty |
| HTTP Client | HTTPX (sync + async) — prefer over Requests |
| Async utilities | Asyncer (`asyncify` / `syncify`) — prefer over asyncio / AnyIO directly |

Run the toolchain with `uv run ruff check app`, `uv run ruff format app`, `uv run ty check app`.

> `E712` is disabled on purpose. In SQLAlchemy, `Model.col == False` is the correct way to
> build a SQL predicate — ruff's suggested `not Model.col` evaluates in Python and silently
> produces the wrong query.

### Frontend
| Concern | Technology |
|---------|-----------|
| Framework | Next.js (App Router) |
| Server State | React Query (TanStack Query) |
| Client State | Zustand (UI-only state) |
| Styling | Tailwind CSS |
| Forms | React Hook Form + Zod |
| Testing | Vitest + Playwright |

---

## 2. Project Structure

```
<project_name>/
├── app/
│   ├── core/                        # Shared infrastructure — never project-specific
│   │   ├── main.py                  # App factory + lifespan
│   │   ├── settings.py              # Pydantic BaseSettings
│   │   ├── database.py              # Async engine + session factory
│   │   ├── models.py                # DeclarativeBase
│   │   ├── crud/                    # Generic CRUD + pagination helpers
│   │   │   ├── base.py              # CRUDBase[Model, Create, Update]
│   │   │   └── helpers.py           # paginated_select(), apply_sorting()
│   │   ├── schemas.py               # ListParams + SortOrder (list-endpoint base)
│   │   ├── exceptions.py            # Global exception handlers
│   │   ├── middleware.py            # CORS, GZip, TrustedHost, timing
│   │   ├── logging.py               # Logger factory
│   │   ├── metrics.py               # Prometheus
│   │   ├── utils.py                 # utc_now(), shared helpers
│   │   ├── alembic_models_import.py # Single file to register ALL models for Alembic
│   │   ├── background/              # Celery app + task infrastructure
│   │   ├── cache/                   # Redis abstraction
│   │   └── object_storage/          # S3-compatible storage
│   │
│   ├── apis/
│   │   └── v1.py                    # Aggregates all module routers
│   │
│   ├── user/                        # Auth + RBAC (included in template)
│   │   ├── models.py                # User, Role, Permission, RefreshToken
│   │   ├── seed.py                  # Idempotent role/permission seeder
│   │   ├── auth_management/         # Login, refresh, logout
│   │   ├── permission_management/   # RBAC + scoped access
│   │   ├── crud/, schemas/, services/, routes/
│   │   └── create_admin.py          # Super-admin CLI
│   │
│   ├── activity/                    # Append-only audit log (included in template)
│   ├── release_notes/               # What's New system (included in template)
│   │
│   └── <feature>/                   # Project-specific domain modules
│       ├── __init__.py              # Public API exports only
│       ├── dependencies.py          # ⚠️ REQUIRED — DI wiring (CRUD→Service, cross-module)
│       ├── models.py                # SQLAlchemy ORM (or models/ subpackage)
│       ├── schemas.py               # Pydantic models (or schemas/ subpackage)
│       ├── crud.py                  # Repository (or crud/ subpackage)
│       ├── services.py              # Business logic (or services/ subpackage)
│       ├── routes.py                # HTTP endpoints (or routes/ subpackage)
│       ├── exceptions.py            # Domain-specific errors
│       ├── enums.py                 # Domain enums
│       ├── permissions.py           # Permission constants
│       └── tasks.py                 # Celery tasks
│
├── migrations/
│   ├── env.py
│   └── versions/                    # YYYY_MM_DD_HHMM-<rev>_<slug>.py
│
├── docker/
│   ├── Dockerfile                   # Multi-stage: builder → runtime (non-root appuser)
│   ├── docker-entrypoint.sh
│   ├── celery-worker-entrypoint.sh
│   └── flower-entrypoint.sh
│
├── docs/
├── logs/                            # Gitignored runtime logs
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

### Frontend
```
src/
├── app/                             # Next.js App Router
│   ├── (auth)/                      # Unauthenticated pages
│   ├── (dashboard)/
│   │   └── <role>/                  # One folder per user role
│   │       ├── config.ts            # Nav items, route constants — NO JSX, no hooks
│   │       ├── layout.tsx
│   │       └── <feature>/page.tsx
│   ├── api/                         # Route handlers (BFF layer)
│   └── globals.css                  # Design tokens — single source of truth
│
├── components/
│   ├── layout/                      # Shell (sidebar, topnav)
│   ├── providers/                   # Context wrappers — no visual output
│   ├── shared/                      # Reusable feature components
│   └── ui/                          # Primitives (Button, Badge, Input)
│
├── lib/                             # Business logic — DOMAIN-BASED
│   ├── api-client.ts                # Singleton HTTP client — stateless, no stored tokens
│   └── <domain>/
│       ├── types.ts                 # Backend* (snake_case) + Frontend (camelCase) types
│       ├── transformers.ts          # snake_case ↔ camelCase — the ONLY place backend fields appear
│       ├── api.ts                   # Service functions → apiClient → transform → return
│       ├── hooks.ts                 # React Query hooks
│       ├── store.ts                 # Zustand — ONLY shared UI state (optional)
│       └── index.ts                 # Barrel exports
│
└── middleware.ts                    # Route protection + API auth injection
```

---

## 3. Naming Conventions

### Backend
| Type | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case.py` | `user_crud.py`, `lead_service.py` |
| Module directories | `snake_case/` | `app/lead/`, `app/release_notes/` |
| Classes | `PascalCase` | `UserService`, `LeadCRUD` |
| Functions/methods | `snake_case` | `get_current_user()`, `create_lead()` |
| Constants | `UPPER_SNAKE_CASE` | `PERMISSIONS`, `API_V1_PREFIX` |
| Pydantic schemas | `PascalCase` + intent suffix | `LeadCreate`, `LeadUpdate`, `LeadResponse` |
| CRUD instances | `<model>_crud` | `user_crud = UserCRUD(User)` |
| DI factories | `get_<name>_service` | `get_lead_service()` in `dependencies.py` |
| Router instances | `<module>_router` | `lead_router = APIRouter(...)` |
| DB tables | `plural_snake_case` | `users`, `refresh_tokens` |
| Index names | `ix_<table>_<columns>` | `ix_users_status` |
| Migration files | `YYYY_MM_DD_HHMM-<rev>_<slug>.py` | `2026_02_09_0657-8600ba4ec5f7_user_init.py` |
| Permissions | `resource:action[:scope]` | `leads:create`, `leads:view:all` |

### Frontend
| Type | Convention | Example |
|------|-----------|---------|
| Files | `kebab-case.tsx` or `camelCase.ts` | `lead-table.tsx`, `hooks.ts` |
| Components | `PascalCase` | `LeadTable`, `UserAvatar` |
| Hooks | `use` prefix | `useLeads()`, `useCreateLead()` |
| Backend types | `Backend*` prefix | `BackendLead`, `BackendUser` |

---

## 4. Layered Architecture

```
Route → Service → CRUD → Model
```

| Layer | Responsibility | Hard Rules |
|-------|---------------|------------|
| **Routes** | Parse HTTP, call service, return response | No business logic. No direct DB queries. Use `Depends()` for everything. |
| **Services** | Business logic, orchestration | Owns `commit()` / `rollback()`. Never import FastAPI types. |
| **CRUD** | SQL operations | Never `session.commit()`. Only `add()`, `flush()`, `refresh()`. Extend `CRUDBase`. |
| **Schemas** | Request/response shapes | Split by intent: `Create`, `Update`, `Response`. |
| **Models** | Database tables | Pure data containers. No business logic. |

### Transaction ownership

```python
# ✅ Service commits
async def create_lead(session, data):
    lead = await lead_crud.create(session, obj_in=data)
    await session.commit()   # service owns this
    return lead

# ❌ CRUD never commits
async def create(self, session, obj_in):
    await session.commit()   # NEVER
```

### CRUDBase pattern

```python
class LeadCRUD(CRUDBase[Lead, LeadCreate, LeadUpdate]):
    async def get_by_email(self, session, email: str) -> Lead | None:
        ...

lead_crud = LeadCRUD(Lead)   # module-level singleton
```

### Return types (not `response_model`)

Always declare a return type on route functions — Pydantic serialises the response on the Rust side, which is faster and ensures sensitive fields are filtered automatically.

```python
# ✅ preferred — serialised by Pydantic via return type
@router.get("/")
async def list_leads(
    service: LeadServiceDep,
    session: SessionDep,
) -> list[LeadResponse]:
    return await service.list_leads(session)
```

Use `response_model=` only when the return annotation cannot express what you want (e.g. returning `Any` while filtering to a specific schema):

```python
@router.get("/me", response_model=UserPublic)
async def get_me(...) -> Any:
    return internal_user_object   # InternalUser has extra secret fields
```

Never use `ORJSONResponse` or `UJSONResponse` — they are deprecated; Pydantic's Rust serialiser via return types is faster.

### Async vs sync route functions

Use `async def` only when the function body calls actual async code (awaited coroutines, async DB operations, etc.).  
Use plain `def` — which FastAPI runs in a threadpool — for any blocking I/O or when in doubt.  
Never run blocking code inside an `async def` function; it will stall the event loop.

```python
# ✅ async — awaiting an async DB call
@router.get("/{lead_id}")
async def get_lead(lead_id: UUID, service: LeadServiceDep, session: SessionDep) -> LeadResponse:
    return await service.get_lead(session, lead_id)

# ✅ plain def — blocking / sync-only code, runs in threadpool
@router.get("/export")
def export_leads_csv(service: LeadServiceDep, session: SessionDep) -> StreamingResponse:
    data = service.build_csv_sync(session)
    ...
```

When you must mix blocking and async code, use **Asyncer** (`asyncify` / `syncify`) instead of raw `asyncio` or `anyio`.

---

## 5. Dependency Injection (`dependencies.py`)

Every module **must** have a `dependencies.py`. It is the single wiring layer — the only file that knows about cross-module imports.

```
Route ──Depends()──▶ Service ──constructor──▶ CRUD ──Depends()──▶ Session
```

### `Annotated` type aliases

Always declare dependencies as `Annotated` type aliases — they are re-usable, keep signatures readable, and work correctly in non-FastAPI contexts (tests, scripts).

```python
# app/core/database.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
```

```python
# app/user/dependencies.py
from typing import Annotated
from fastapi import Depends
from app.user.user.models import User

CurrentUserDep = Annotated[User, Depends(get_current_active_user)]
```

```python
# app/lead/dependencies.py  ← the ONLY file that imports across modules
from typing import Annotated
from fastapi import Depends
from app.lead.crud import lead_crud
from app.user.user.crud import user_crud   # cross-module import lives here

def get_lead_service() -> LeadService:
    return LeadService(lead_crud=lead_crud, user_crud=user_crud)

LeadServiceDep = Annotated[LeadService, Depends(get_lead_service)]
```

```python
# app/lead/routes.py — all dependencies via Annotated aliases
@router.post("/")
async def create_lead(
    data: LeadCreate,
    _: Annotated[None, Depends(require_permission("leads:create"))],
    current_user: CurrentUserDep,
    session: SessionDep,
    service: LeadServiceDep,
) -> LeadResponse:
    return await service.create_lead(session, data, current_user)
```

### Service wiring

```python
# app/lead/services.py
class LeadService:
    def __init__(self, lead_crud: LeadCRUD, user_crud: UserCRUD):
        self.lead_crud = lead_crud
        self.user_crud = user_crud   # injected — never imported at module level
```

### Dependencies with `yield` and scope

Use `yield` for dependencies that need cleanup (sessions, file handles).  
The default scope `"request"` runs cleanup after the response is sent.  
Use `scope="function"` to run cleanup after response data is generated but **before** the response is sent (useful for pre-send side effects).

`scope` is an argument to **`Depends()`**, never a parameter of the dependency function —
declaring it on the function turns `scope` into a query parameter.

```python
from typing import Annotated
from fastapi import Depends

# Default — cleanup after the response is sent (most common)
async def get_session():
    async with async_session_factory() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# scope="function" — cleanup before the response leaves the server
def get_audit_writer():
    writer = AuditWriter()
    try:
        yield writer
    finally:
        writer.flush()   # runs before the response is sent

AuditWriterDep = Annotated[AuditWriter, Depends(get_audit_writer, scope="function")]
```

```python
# ❌ never — `scope` becomes a query parameter, and the dependency keeps request scope
def get_audit_writer(scope="function"):
    ...
```

**Sub-dependency rule:** a `scope="request"` dependency may only depend on other
`scope="request"` dependencies. A `scope="function"` dependency may depend on both.

Requires FastAPI >= 0.121.0.

### Class dependencies

Avoid injecting class instances directly via `Depends(ClassName)`. Instead, create a factory function that returns an instance.

```python
# ✅ factory function returning a dataclass/instance
from dataclasses import dataclass
from typing import Annotated
from fastapi import Depends

@dataclass
class QueryParams:
    offset: int = 0
    limit: int = 100
    q: str | None = None

def get_query_params(offset: int = 0, limit: int = 100, q: str | None = None) -> QueryParams:
    return QueryParams(offset=offset, limit=limit, q=q)

QueryParamsDep = Annotated[QueryParams, Depends(get_query_params)]

# ❌ avoid — class used directly as dependency
# Annotated[QueryParams, Depends()]   ← do not do this
```

For a **bundle of query parameters**, skip `Depends()` entirely and bind a Pydantic model
as a query-parameter model. This is the idiom §10 uses for list endpoints:

```python
async def list_leads(params: Annotated[LeadListParams, Query()]) -> list[LeadResponse]:
    ...
```

FastAPI flattens the model into individual query parameters in OpenAPI, so the docs render
one input per field rather than a request body.

**Rules:**
- All dependencies declared as `Annotated` type aliases
- Cross-module imports happen ONLY in `dependencies.py`
- Services receive CRUD via constructor — never global import
- Routes receive services via `Dep` alias — never direct instantiation
- `dependencies.py` contains only factory functions — no business logic, no DB queries

---

## 6. Model Standards

```python
from app.core.models import Base
from app.core.utils import utc_now

class MyModel(Base):
    __tablename__ = "my_models"
    __table_args__ = (
        Index('ix_my_models_field', 'field'),   # always name indexes explicitly
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- Always UUID primary keys
- Always `DateTime(timezone=True)` — store UTC, let frontend convert for display
- Default: `utc_now` from `app.core.utils` — never `datetime.utcnow()` (deprecated)

---

## 7. Settings & Configuration

- `app/core/settings.py` — Pydantic `BaseSettings`, loaded from `.env`
- Group fields with section comments: `# === Database ===`
- Required secrets have no default (fail fast): `SECRET_KEY: str = Field(...)`
- Computed values use `@property`; cache instance with `@lru_cache()`
- All env vars documented in `.env.example` with inline comments

---

## 8. Database & Alembic

### Alembic model registration

`app/core/alembic_models_import.py` is the single source of truth for autogenerate:

```python
from app.core.models import Base
from app.user.user.models import User, UserRole
from app.user.permission_management.models import Permission, Role, RolePermission
from app.user.auth.models import RefreshToken, OAuthAccount, PhoneOTP
from app.activity.models import ActivityLog
from app.release_notes.models import ReleaseNote
# from app.mymodule.models import MyModel   ← add here
```

`migrations/env.py` does `from app.core.alembic_models_import import *` — never add models directly to `env.py`.

### Migration naming

Configured in `alembic.ini`:
```ini
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
```

---

## 9. Authentication & RBAC

### Permission naming

```python
PERMISSIONS = [
    # (resource, action, description)
    ("leads", "view",     "View lead details"),
    ("leads", "view:all", "View all leads"),
]
# Stored as: "leads:view", "leads:view:all"
```

### Seed script (`app/user/seed.py`)

- **Idempotent** — only inserts missing data; safe to re-run
- Runs automatically on startup via `lifespan` in `main.py`
- `super_admin` bypasses all permission checks
- `is_system=True` roles cannot be deleted via UI
- All project-specific roles/permissions defined here — nowhere else

### Route permission guard

Prefer a router-level guard when every route in the module shares it (§11); use a
per-route guard only for narrower permissions. Either way, dependencies are declared as
`Annotated` aliases — never inline `Depends()` defaults (§5).

```python
# Shared guard for the whole module
lead_router = APIRouter(
    prefix="/leads",
    tags=["Leads"],
    dependencies=[Depends(require_permission("leads:view"))],
)

# Narrower guard on a single route
RequireLeadCreate = Annotated[None, Depends(require_permission("leads:create"))]

@lead_router.post("")
async def create_lead(
    data: LeadCreate,
    _: RequireLeadCreate,
    current_user: CurrentUserDep,
    session: SessionDep,
    service: LeadServiceDep,
) -> LeadResponse:
    return await service.create_lead(session, data, current_user)
```

---

## 10. List Endpoints (Filtering, Sorting, Pagination)

> Adopt this when a module's list endpoint grows past two or three filters. Simple lists
> (see `activity`, `release_notes`, `user`) declare flat `Annotated[..., Query()]` parameters
> and don't need a params model.

Every list endpoint uses this standard flow:

```
Route (params: Annotated[XxxListParams, Query()])
  └─ Service (pass-through + business-rule overrides)
       └─ CRUD.get_list_filtered(session, skip, limit, sort_by, sort_order, …filters)
            └─ paginated_select → single SQL with COUNT(*) OVER ()
            └─ Returns (items: list, total: int)
```

### Required pieces per module

| File | What to add |
|------|-------------|
| `schemas.py` | `XxxListParams(ListParams)` — narrow `sort_by` to a `Literal[...]` + add filters |
| `crud.py` | `get_list_filtered(…)` — builds filters, calls `paginated_select()` or `apply_sorting()` |
| `services.py` | `list_xxx(session, params, …)` — pass-through |
| `routes.py` | `params: Annotated[XxxListParams, Query()]` |

```python
class LeadListParams(ListParams):
    sort_by: Optional[Literal["created_at", "updated_at", "status"]] = None
    search: Optional[str] = None
    status: Optional[str] = None
```

Narrow `sort_by` with a `Literal[...]` of the columns the resource actually allows sorting
by — not a `str` and not an `Enum`. OpenAPI renders it as a typed dropdown, and an invalid
column is rejected as a 422 at the route layer instead of being silently mapped to the
default inside CRUD. `SortOrder` in `app/core/schemas.py` is likewise a `Literal["asc", "desc"]`.

Bind it with `Query()`, never `Depends()`:

```python
@lead_router.get("")
async def list_leads(
    params: Annotated[LeadListParams, Query()],
    session: SessionDep,
    service: LeadServiceDep,
) -> LeadListResponse:
    return await service.list_leads(session, params)
```

```python
# ❌ never — this is the class-dependency anti-pattern (§5)
async def list_leads(params: LeadListParams = Depends()):
    ...
```

- Always append `model.id.desc()` as tiebreaker in `order_clauses` (prevents duplicate rows across pages)
- `ListParams` is declared `frozen=True`, so mutating `params` raises. Apply business-rule
  scope overrides with a copy:

```python
# ✅ service narrows the query to what this user may see
scoped = params.model_copy(update={"owner_id": current_user.id})
```

---

## 11. API Router Registration

Declare `prefix`, `tags`, and shared `dependencies` on the router itself — not on `include_router()`. This keeps the module self-contained and the aggregation file clean.

```python
# app/lead/routes.py
lead_router = APIRouter(
    prefix="/leads",
    tags=["Leads"],
    dependencies=[Depends(require_permission("leads:view"))],  # shared guard
)
```

```python
# app/apis/v1.py
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(activity_router)
router.include_router(lead_router)
# router.include_router(mymodule_router)   ← add new modules here
```

Mounted in `core/main.py`:
```python
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)  # /api/v1
```

---

## 12. Background Tasks (Celery)

- Module tasks: `app/<module>/tasks.py`
- Infrastructure (config, base task): `app/core/background/`
- Celery reference path: `app.core.background.celery_app:celery_app`
- Use `app/core/background/internals/session.py` for DB sessions in tasks — not the FastAPI `get_session`

---

## 13. Exception Handling

```python
# app/<feature>/exceptions.py
class LeadNotFoundException(HTTPException):
    def __init__(self, lead_id: str):
        super().__init__(status_code=404, detail=f"Lead {lead_id} not found")
```

- Each module defines domain exceptions in `exceptions.py`
- Never raise raw `HTTPException(500)` from services
- `app/core/exceptions.py` handles: 422 (validation), 409 (integrity), 503 (operational), 500 (sqlalchemy), 400 (value), 403 (permission), 500 (catch-all)

---

## 14. Logging

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
logger.info("User created", extra={"user_id": str(user.id)})
logger.error("DB write failed", exc_info=True)
```

Log files: `logs/<APP_NAME>.log` (all, rotating), `logs/<APP_NAME>_errors.log` (errors only)

---

## 15. Streaming

### JSON Lines

Declare a return type of `AsyncIterable[Model]` and `yield` items — FastAPI handles the chunked response automatically.

```python
from collections.abc import AsyncIterable

@router.get("/stream")
async def stream_leads(session: SessionDep, service: LeadServiceDep) -> AsyncIterable[LeadResponse]:
    async for lead in service.stream_leads(session):
        yield lead
```

### Server-Sent Events (SSE)

Use `response_class=EventSourceResponse` and `yield` Pydantic model instances (auto-serialised as `data:` fields).

```python
from collections.abc import AsyncIterable
from fastapi.sse import EventSourceResponse

@router.get("/events", response_class=EventSourceResponse)
async def lead_events(session: SessionDep) -> AsyncIterable[LeadResponse]:
    async for lead in watch_leads(session):
        yield lead
```

For full SSE control (`event`, `id`, `retry`), yield `ServerSentEvent` instances:

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@router.get("/progress", response_class=EventSourceResponse)
async def progress_stream() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(data={"status": "started"}, event="status", id="1")
    yield ServerSentEvent(data={"progress": 50}, event="progress", id="2")
```

Use `raw_data` instead of `data` to send pre-formatted strings without JSON encoding.

### Byte streaming

Subclass `StreamingResponse` with the correct `media_type` and use `yield from` — do not return a `StreamingResponse` instance directly.

```python
from fastapi.responses import StreamingResponse

class PNGStreamingResponse(StreamingResponse):
    media_type = "image/png"

@router.get("/image", response_class=PNGStreamingResponse)
def stream_image():
    with open_image() as f:
        yield from f
```

Do not annotate the return type here — the function is a generator, not a function that
returns a response object, so `-> PNGStreamingResponse` is false and `ty` will flag it.

---

## 16. Frontend Patterns

### Data flow

```
Component → Hook (hooks.ts) → Service (api.ts) → apiClient → Backend
```

- All requests through `apiClient`. No direct `fetch()` in components.
- `apiClient` is stateless — never stores tokens. Auth handled by `middleware.ts`.
- All snake_case → camelCase conversion happens once, in `transformers.ts`.
- Components never see backend shapes.

### State management

```
Data from API + interactive?  → React Query
Data from API, initial load?  → Server Component (RSC)
Shared UI-only state?         → Zustand
Local component state?        → useState
```

Never put API data (`isLoading`, `error`, `items[]`) in Zustand.

### React Query pattern

```typescript
export const leadKeys = {
  lists: () => ["leads", "list"] as const,
  list: (params) => [...leadKeys.lists(), params] as const,
};

export function useLeads(params) {
  return useQuery({ queryKey: leadKeys.list(params), queryFn: () => leadApi.list(params), staleTime: 30_000 });
}

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: leadApi.create, onSuccess: () => qc.invalidateQueries({ queryKey: leadKeys.lists() }) });
}
```

### Error handling

All API errors are `AppError` instances (statusCode, message, detail, data). Map 422 responses to field errors. Use `onError` in mutations, not try/catch in components.

### Styling rules

- All tokens in `globals.css`. Use semantic tokens: `text-primary`, `bg-muted`.
- Never hex colors or `bg-[#f5f5f5]` in component files.

### File size limits

| Type | Max |
|------|-----|
| Page component | ~200 lines |
| Shared component | ~150 lines |
| Custom hook | ~80 lines |
| Zustand store | ~50 lines (if more, you're storing server state) |

---

## 17. Docker

| Service | Image | Port |
|---------|-------|------|
| `api` | custom Dockerfile | `${API_PORT:-8000}` |
| `postgres` | `postgres:16-alpine` | `${POSTGRES_PORT:-5432}` |
| `redis` | `redis:7-alpine` | `${REDIS_PORT:-6379}` |
| `celery_worker` | custom Dockerfile | — |
| `flower` | custom Dockerfile | `${FLOWER_PORT:-5555}` |

- Networks and volumes prefixed with project name: `<project>_network`, `<project>_postgres_data`
- Dockerfile: multi-stage — builder (`uv pip install`) → runtime (non-root `appuser`, uid 1000)

---

## 18. New Feature Checklist

### Backend

```
□ Create app/<feature>/ with __init__.py
□ Define schemas (Create, Update, Response)
□ Define ORM model
□ Register model in app/core/alembic_models_import.py
□ alembic revision --autogenerate -m "<desc>" && alembic upgrade head
□ Implement CRUD extending CRUDBase
□ Implement service (receives CRUD via constructor, owns commit)
□ Create dependencies.py (wire CRUD → service, declare cross-module deps)
□ Define domain exceptions in exceptions.py
□ Add permissions in app/user/seed.py (PERMISSIONS + ROLE_PERMISSIONS)
□ Define routes (inject service via Depends(get_<name>_service))
□ Register router in app/apis/v1.py
□ Export public API in __init__.py
□ Write tests
```

### Frontend

```
□ Create lib/<domain>/ folder
□ types.ts — Backend* (snake_case) + Frontend (camelCase) types
□ transformers.ts — manual mapping only, no auto-mappers
□ api.ts — service functions → apiClient → transform → return
□ hooks.ts — query key factory + useQuery/useMutation
□ store.ts — ONLY if shared UI state needed (never API data)
□ index.ts — barrel exports
□ Page at app/(dashboard)/<role>/<feature>/page.tsx
□ Add nav item + route constant to role's config.ts
```

---

## 19. Hard Rules

### Backend — never do
- Business logic in routes
- `session.commit()` in CRUD layer
- `datetime.utcnow()` — use `utc_now()` from `app.core.utils` (§6)
- Hardcoded secrets or config values
- Raw SQL strings — always use SQLAlchemy ORM/Core
- Skip the service layer (route → CRUD directly)
- Project-specific code in `app/core/`
- Forget to register models in `alembic_models_import.py`
- Forget to register routers in `app/apis/v1.py`
- Cross-module imports in services — that belongs in `dependencies.py`
- Instantiate services directly in routes — always inject via the service's `Dep` alias
- Create a module without `dependencies.py`
- Inline `Depends()` in route signatures — declare `Annotated` type aliases instead
- Use `...` (Ellipsis) as a default in path operations or Pydantic fields — omit the default entirely
- Use `RootModel` — use plain type annotations with `Annotated` + Pydantic validators
- Use `ORJSONResponse` or `UJSONResponse` — they are deprecated; use return type annotations
- Run blocking code inside `async def` route functions — use plain `def` or Asyncer
- Multiple HTTP methods in a single function (`api_route` with `methods=[...]`) — one function per HTTP operation
- Set `prefix`/`tags` in `include_router()` when they can be set on the router itself
- Use `Requests` for outbound HTTP — use HTTPX
- Use raw `asyncio` or `anyio` to bridge sync ↔ async in a request path — use Asyncer
  (`asyncify` / `syncify`). Event-loop *lifecycle* management is exempt: Celery workers
  (`core/background/`) and CLI entrypoints (`seed.py`, `create_admin.py`) legitimately call
  `asyncio.run()` / manage their own loop, because there is no running loop to bridge into
- Bind a bundle of query parameters with `Depends()` — use `Annotated[Model, Query()]` (§10)
- Declare `scope` as a parameter of a dependency function — it belongs on `Depends()` (§5)
- Use `python-jose` or `passlib` — both are unmaintained; use PyJWT and pwdlib (§1)

### Frontend — never do
- API data in Zustand (`isLoading`, `error`, `items[]`, `fetchX()`)
- Direct `fetch()` in components
- Hex colors in component files — use design tokens
- Backend `snake_case` fields leaking into components
- Tokens stored in `apiClient`
- Deep relative imports (`../../..`) — use `@/` aliases
- `any` without an explaining comment
- JSX or hooks in `config.ts`
- Mixing Server Actions + React Query mutations for the same operation

### Both — never do
- Files exceeding 200 lines without extracting sub-modules
- Generate code without reading existing code first
- Add unrequested features, refactors, or abstractions

---

## 20. What Goes Where

| Question | Answer |
|----------|--------|
| Applies to every project? | `app/core/` |
| Authentication / user management? | `app/user/` |
| Audit trail of events? | `app/activity/` |
| Version change announcements? | `app/release_notes/` |
| Feature-specific business logic? | `app/<feature>/services/` |
| DB row definition? | `app/<feature>/models/` |
| API contract shape? | `app/<feature>/schemas/` |
| Who can do what? | `app/<feature>/permissions.py` + `user/seed.py` |
| Background task? | `app/<feature>/tasks.py` |
| FastAPI `Depends()` wiring? | `app/<feature>/dependencies.py` |

---

## 21. Deviations from the Official FastAPI Skill

These conventions are checked against the [official FastAPI agent skill](https://github.com/fastapi/fastapi/blob/master/fastapi/.agents/skills/fastapi/SKILL.md).
Where we knowingly differ, the reason is recorded here — **do not "fix" these to match the skill.**

| Skill says | We do | Why |
|------------|-------|-----|
| Prefer **SQLModel** over SQLAlchemy | SQLAlchemy 2.0 (async) | `CRUDBase[Model, Create, Update]` generics, Alembic autogenerate, the RBAC join tables, and `paginated_select()` are all built on SQLAlchemy Core. SQLModel would be a rewrite of the template's foundation for no functional gain, and its `table=True` models blur the schema/model split that §4 depends on. |
| Use `fastapi dev` / `fastapi run` with a `[tool.fastapi]` entrypoint | `uvicorn app.core.main:app` via Docker Compose | Deployment is containerized; the process is supervised by Compose and the entrypoint scripts in `docker/`. The CLI adds a layer we don't use. |
| Serve built frontends with `app.frontend()` | Frontend deployed separately | The frontend is a Next.js SSR app, not a static build directory. `app.frontend()` only serves built static assets. |

Everything else in the skill applies, including the sections it defers to its reference docs:
`dependencies`, `responses`, `pydantic`, `path-operations`, `streaming`, and `other-tools`.

### Minimum FastAPI version

Conventions in this document depend on these releases — keep the floor in `pyproject.toml`
at or above the highest one you rely on:

| Convention | Requires |
|------------|----------|
| `Depends(..., scope=...)` (§5) | 0.121.0 |
| JSON Lines / byte streaming via `yield` (§15) | 0.134.0 |
| `fastapi.sse` — `EventSourceResponse`, `ServerSentEvent` (§15) | 0.135.0 |
