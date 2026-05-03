# Project Conventions

> Authoritative guide for building and scaling modules in this FastAPI + Next.js stack.
> Applies to AI coding assistants and human developers equally — these are hard constraints.

---

## Reference Resources

| Resource | URL | Purpose |
|----------|-----|---------|
| Backend Template | https://github.com/hybridinteract/fastapi-template | Production-ready starter — clone this, never rebuild from scratch |
| Project Structure Standards | https://engineering.hybridinteractive.in/standards/project-structure/ | Canonical modular monolith + DDD guide |

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
| Caching | Redis |
| Background Tasks | Celery + Flower |
| Config | Pydantic Settings (env-based) |
| Storage | S3-compatible (boto3) |
| Monitoring | Prometheus |
| Package Manager | uv |

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

---

## 5. Dependency Injection (`dependencies.py`)

Every module **must** have a `dependencies.py`. It is the single wiring layer — the only file that knows about cross-module imports.

```
Route ──Depends()──▶ Service ──constructor──▶ CRUD ──Depends()──▶ Session
```

```python
# app/lead/services.py
class LeadService:
    def __init__(self, lead_crud: LeadCRUD, user_crud: UserCRUD):
        self.lead_crud = lead_crud
        self.user_crud = user_crud   # injected — not imported at module level
```

```python
# app/lead/dependencies.py  ← the ONLY file that imports across modules
from app.lead.crud import lead_crud
from app.user.crud import user_crud   # cross-module import lives here

def get_lead_service() -> LeadService:
    return LeadService(lead_crud=lead_crud, user_crud=user_crud)
```

```python
# app/lead/routes.py
@router.post("/")
async def create_lead(
    data: LeadCreate,
    _: None = Depends(require_permission("leads:create")),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    service: LeadService = Depends(get_lead_service),
):
    return await service.create_lead(session, data, current_user)
```

**Rules:**
- Cross-module imports happen ONLY in `dependencies.py`
- Services receive CRUD via constructor — never global import
- Routes receive services via `Depends(get_<name>_service)` — never direct instantiation
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
from app.user.models import User, Role, Permission, RefreshToken
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

```python
@router.get("/")
async def list_leads(
    _: None = Depends(require_permission("leads:view")),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    service: LeadService = Depends(get_lead_service),
):
    ...
```

---

## 10. List Endpoints (Filtering, Sorting, Pagination)

Every list endpoint uses this standard flow:

```
Route (XxxListParams = Depends())
  └─ Service (pass-through + business-rule overrides)
       └─ CRUD.get_list_filtered(session, skip, limit, sort_by, sort_order, …filters)
            └─ paginated_select → single SQL with COUNT(*) OVER ()
            └─ Returns (items: list, total: int)
```

### Required pieces per module

| File | What to add |
|------|-------------|
| `enums.py` | `XxxSortField(str, Enum)` |
| `schemas.py` | `XxxListParams(ListParams)` — override `sort_by` + add filters |
| `crud.py` | `get_list_filtered(…)` — builds filters, calls `paginated_select()` or `apply_sorting()` |
| `services.py` | `list_xxx(session, params, …)` — pass-through |
| `routes.py` | `params: XxxListParams = Depends()` |

```python
class LeadListParams(ListParams):
    sort_by: LeadSortField = LeadSortField.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC
    search: Optional[str] = None
    status: Optional[str] = None
```

- Always append `model.id.desc()` as tiebreaker in `order_clauses` (prevents duplicate rows across pages)
- Pydantic models are immutable — use a local variable for scope overrides, never mutate `params`

---

## 11. API Router Registration

```python
# app/apis/v1.py
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(activity_router, prefix="/activity-logs", tags=["Activity Logs"])
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

## 15. Frontend Patterns

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

## 16. Docker

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

## 17. New Feature Checklist

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

## 18. Hard Rules

### Backend — never do
- Business logic in routes
- `session.commit()` in CRUD layer
- `datetime.utcnow()` — use `datetime.now(timezone.utc)`
- Hardcoded secrets or config values
- Raw SQL strings — always use SQLAlchemy ORM/Core
- Skip the service layer (route → CRUD directly)
- Project-specific code in `app/core/`
- Forget to register models in `alembic_models_import.py`
- Forget to register routers in `app/apis/v1.py`
- Cross-module imports in services — that belongs in `dependencies.py`
- Instantiate services directly in routes — always `Depends(get_<name>_service)`
- Create a module without `dependencies.py`

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

## 19. What Goes Where

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
