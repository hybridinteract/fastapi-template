# AI Coding Assistant — Enterprise Project Instructions

> **Purpose:** This document is a system-level constraint file for AI coding assistants (Cursor, Copilot, Claude Code, etc.). Every rule below is a **hard constraint** — never violate them, even if the user's prompt is ambiguous. When in doubt, follow this document over general coding intuition.

### Reference Resources

| Resource | URL | Purpose |
|----------|-----|---------|
| Backend Template | https://github.com/hybridinteract/fastapi-template | Production-ready FastAPI starter with auth, RBAC, Celery, caching, storage, and deployment configs. Clone this to start any new backend. |
| Project Structure Standards | https://engineering.hybridinteractive.in/standards/project-structure/ | Canonical guide for modular monolith architecture with DDD principles. |


> **When starting a new backend project:** Clone the template repo above. It includes a complete `user` module (auth + RBAC), `activity` logging, `release_notes`, Celery infrastructure, Redis caching, S3 storage, Prometheus metrics, Docker + deployment configs, and all `app/core/` infrastructure. **Never rebuild these from scratch** — extend what the template provides.

---

## Table of Contents

1. [General Principles](#1-general-principles)
2. [Backend Architecture (FastAPI)](#2-backend-architecture-fastapi)
3. [Frontend Architecture (Next.js)](#3-frontend-architecture-nextjs)
4. [Shared Rules](#4-shared-rules)
5. [Hard Don'ts (Global)](#5-hard-donts-global)
6. [New Feature Checklists](#6-new-feature-checklists)

---

## 1. General Principles

These apply to **every file** you generate or modify, backend or frontend.

1. **Domain colocation** — Group code by business domain/feature, never by technical layer. All code for "leads" lives together.
2. **Separation of concerns** — HTTP handling, business logic, and data access are strictly isolated into independent layers.
3. **Explicit over implicit** — Type everything. Name every constant. No `any`. No magic strings. No raw dictionaries as return types.
4. **Single responsibility** — One component/service/model per file. One store per domain. One transformer per domain.
5. **Minimal coupling** — Domains are self-contained. A change in `leads/` never requires touching `meetings/`.
6. **No over-engineering** — Only build what is asked. No speculative abstractions, feature flags for one-off features, or "helper" files for single-use logic. Three similar lines > a premature abstraction.
7. **No silent failures** — Never swallow errors. Always surface them (toast, log, or re-raise).
8. **File size limits** — No single file should exceed **200 lines**. If it does, extract sub-components, sub-services, or helper modules into the same folder.

---

## 2. Backend Architecture (FastAPI)

### 2.1 Tech Stack

| Concern | Technology |
|---------|-----------|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL via asyncpg |
| Migrations | Alembic (async) |
| Validation | Pydantic v2 |
| Auth | JWT (access + refresh tokens) + RBAC |
| Caching | Redis |
| Background Tasks | Celery + Flower |
| Config | Pydantic Settings (env-based) |
| Storage | S3-compatible (boto3) |
| Monitoring | Prometheus |
| Package Manager | uv |

### 2.2 Project Structure

```
app/
├── core/                          # Shared infrastructure — NEVER put project-specific logic here
│   ├── main.py                    # App factory + lifespan
│   ├── settings.py                # Pydantic Settings
│   ├── database.py                # Async engine + session factory
│   ├── models.py                  # DeclarativeBase
│   ├── crud.py                    # Generic CRUDBase[Model, Create, Update]
│   ├── exceptions.py              # Global exception handlers
│   ├── middleware.py              # CORS, GZip, TrustedHost, timing
│   ├── logging.py                 # Logger factory
│   ├── metrics.py                 # Prometheus
│   ├── utils.py                   # utc_now(), shared helpers
│   ├── alembic_models_import.py   # Single place to register ALL models
│   ├── background/                # Celery infrastructure
│   ├── cache/                     # Redis abstraction
│   └── object_storage/            # S3-compatible storage
│
├── apis/
│   └── v1.py                      # Aggregates all module routers
│
├── user/                          # Auth + RBAC (included in template)
│   ├── models.py
│   ├── exceptions.py
│   ├── seed.py                    # Idempotent role/permission seeder
│   ├── auth_management/           # Login, refresh, logout
│   ├── permission_management/     # RBAC + scoped access
│   ├── crud/
│   ├── schemas/
│   ├── services/
│   └── routes/
│
├── activity/                      # Audit log (included in template)
├── release_notes/                 # What's New (included in template)
│
└── <feature>/                     # YOUR domain modules go here
    ├── __init__.py                # Public API exports only
    ├── dependencies.py            # ⚠️ REQUIRED — DI wiring (CRUD→Service, cross-module deps)
    ├── models.py                  # SQLAlchemy ORM (or models/ subpackage)
    ├── schemas.py                 # Pydantic models (or schemas/ subpackage)
    ├── crud.py                    # Repository (or crud/ subpackage)
    ├── services.py                # Business logic (or services/ subpackage)
    ├── routes.py                  # HTTP endpoints (or routes/ subpackage)
    ├── exceptions.py              # Domain-specific errors
    ├── enums.py                   # Domain enums
    └── tasks.py                   # Celery tasks
```

### 2.3 Layer Rules (STRICT — Never Skip Layers)

```
Route → Service → CRUD → Model
```

| Layer | Responsibility | Hard Rules |
|-------|---------------|------------|
| **Routes** | Parse HTTP input, call service, return response | NO business logic. NO direct DB queries. Use `Depends()` for session + auth. |
| **Services** | Execute business rules, orchestrate operations | OWN transaction boundaries (`commit()` / `rollback()`). Must be HTTP-agnostic — never import FastAPI types. |
| **CRUD** | Encapsulate SQL operations | NEVER call `session.commit()`. Only `session.add()`, `session.flush()`, `session.refresh()`. Extend `CRUDBase`. |
| **Schemas** | Define request/response shapes | Split by intent: `<Name>Create`, `<Name>Update`, `<Name>Response`. One schema per purpose. |
| **Models** | Define database tables | Pure data containers. No business logic inside models. |

### 2.4 Implementation Order for New Features

Always follow this exact sequence:

1. **Schemas** — Define Pydantic models first (Create, Update, Response)
2. **Models** — SQLAlchemy ORM classes
3. **Register model** — Add import to `app/core/alembic_models_import.py`
4. **Migration** — `alembic revision --autogenerate -m "<description>"` then `alembic upgrade head`
5. **CRUD** — Extend `CRUDBase` with domain-specific queries
6. **Services** — Business logic, owns `commit()`
7. **Permissions** — Add to `app/user/seed.py` (PERMISSIONS + ROLE_PERMISSIONS)
8. **Routes** — HTTP endpoints, inject dependencies
9. **Register router** — Add to `app/apis/v1.py`
10. **Tests**

### 2.5 Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case.py` | `user_crud.py`, `lead_service.py` |
| Module directories | `snake_case/` | `app/user/`, `app/lead/` |
| Classes | `PascalCase` | `UserService`, `LeadCRUD` |
| Functions/methods | `snake_case` | `get_current_user()` |
| Constants | `UPPER_SNAKE_CASE` | `PERMISSIONS`, `API_V1_PREFIX` |
| Pydantic schemas | `PascalCase` + intent suffix | `LeadCreate`, `LeadUpdate`, `LeadResponse` |
| CRUD instances | `<model>_crud` | `user_crud = UserCRUD(User)` |
| DI factories | `get_<name>_service` | `get_lead_service()` in `dependencies.py` |
| Router instances | `<module>_router` | `lead_router = APIRouter(...)` |
| DB tables | `plural_snake_case` | `users`, `refresh_tokens` |
| Index names | `ix_<table>_<columns>` | `ix_users_status` |
| Permissions | `resource:action[:scope]` | `leads:create`, `leads:view:all` |

### 2.6 Model Standards

```python
from app.core.models import Base
from app.core.utils import utc_now
from uuid import uuid4

class MyModel(Base):
    __tablename__ = "my_models"

    # Always UUID primary keys
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Always timezone-aware UTC timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Soft delete pattern (when applicable)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Datetime rules:**
- All fields: `DateTime(timezone=True)` — always store with timezone
- Default: `utc_now` from `app.core.utils`
- NEVER use `datetime.utcnow()` (deprecated) — always `datetime.now(timezone.utc)`

### 2.7 CRUD Pattern

```python
from app.core.crud import CRUDBase

class LeadCRUD(CRUDBase[Lead, LeadCreate, LeadUpdate]):
    async def get_by_email(self, session: AsyncSession, email: str) -> Lead | None:
        result = await session.execute(select(self.model).where(self.model.email == email))
        return result.scalar_one_or_none()

lead_crud = LeadCRUD(Lead)  # Module-level singleton
```

### 2.8 Dependency Injection & `dependencies.py` (CRITICAL)

Every module **must** have a `dependencies.py` file. This is the **wiring layer** that makes modules loosely coupled and testable. It defines how CRUD instances are injected into services, how services are injected into routes, and how cross-module dependencies are resolved.

**Why this matters:** Without DI, modules become tightly coupled via direct imports. If `lead/services.py` directly imports `from app.user.crud import user_crud`, then leads and users are permanently entangled. With DI, dependencies are declared as interfaces and injected — making modules independently testable, replaceable, and maintainable.

#### The DI Chain

```
Route ──Depends()──▶ Service ──Depends()──▶ CRUD ──Depends()──▶ Session
```

Every layer receives its dependencies through `Depends()`, never through direct module-level imports of singleton instances.

#### Step 1 — CRUD Singletons (unchanged)

```python
# app/lead/crud.py
from app.core.crud import CRUDBase

class LeadCRUD(CRUDBase[Lead, LeadCreate, LeadUpdate]):
    async def get_by_email(self, session: AsyncSession, email: str) -> Lead | None:
        result = await session.execute(select(self.model).where(self.model.email == email))
        return result.scalar_one_or_none()

lead_crud = LeadCRUD(Lead)  # Module-level singleton — but accessed via DI, not direct import
```

#### Step 2 — Service Receives CRUD via Constructor

```python
# app/lead/services.py
class LeadService:
    def __init__(self, lead_crud: LeadCRUD, user_crud: UserCRUD):
        self.lead_crud = lead_crud
        self.user_crud = user_crud  # Cross-module dependency — injected, not imported

    async def create_lead(self, session: AsyncSession, data: LeadCreate, current_user: User) -> Lead:
        existing = await self.lead_crud.get_by_email(session, data.email)
        if existing:
            raise LeadAlreadyExistsError(data.email)

        lead = await self.lead_crud.create(session, obj_in=data)

        # Service OWNS the commit
        await session.commit()
        await session.refresh(lead)
        return lead
```

**Key:** The service never imports CRUD singletons at the top of the file. It receives them through its constructor.

#### Step 3 — `dependencies.py` Wires Everything Together

```python
# app/lead/dependencies.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.lead.crud import lead_crud
from app.lead.services import LeadService
from app.user.crud import user_crud  # Cross-module CRUD — imported HERE, not in services


def get_lead_service() -> LeadService:
    """Factory that wires CRUD instances into the service."""
    return LeadService(lead_crud=lead_crud, user_crud=user_crud)
```

**This is the ONLY file that knows about cross-module wiring.** If you need to swap `user_crud` for a different implementation (e.g., in tests), you change it in one place.

#### Step 4 — Route Uses `Depends()` for the Service

```python
# app/lead/routes.py
from app.lead.dependencies import get_lead_service

@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: LeadCreate,
    _: None = Depends(require_permission("leads:create")),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    lead_service: LeadService = Depends(get_lead_service),  # Service injected via DI
):
    return await lead_service.create_lead(session, data, current_user)
```

**Routes never instantiate services directly.** Always `Depends(get_<name>_service)`.

#### `dependencies.py` Rules

| Rule | Why |
|------|-----|
| Every module has its own `dependencies.py` | Single place to find all wiring for a domain |
| Cross-module imports happen ONLY in `dependencies.py` | Keeps services/CRUD unaware of other modules |
| Services receive CRUD via constructor, not global import | Enables testing with mock CRUD, enables swapping implementations |
| Routes receive services via `Depends()`, not direct import | Consistent DI chain, testable routes |
| `dependencies.py` contains ONLY factory functions | No business logic, no HTTP logic, no DB queries |
| Factory functions are named `get_<name>_service` or `get_<name>_crud` | Consistent naming across modules |

#### Cross-Module Dependency Example

When `lead` module needs data from `user` module:

```python
# app/lead/dependencies.py
from app.user.crud import user_crud          # ✅ Cross-module import in dependencies.py
from app.lead.crud import lead_crud

def get_lead_service() -> LeadService:
    return LeadService(lead_crud=lead_crud, user_crud=user_crud)
```

```python
# app/lead/services.py
class LeadService:
    def __init__(self, lead_crud: LeadCRUD, user_crud: UserCRUD):
        self.lead_crud = lead_crud
        self.user_crud = user_crud           # ✅ Injected, not imported

    async def assign_lead(self, session, lead_id, user_id):
        user = await self.user_crud.get(session, id=user_id)  # ✅ Uses injected CRUD
        if not user:
            raise UserNotFoundError(user_id)
        # ...
```

```python
# WRONG — tight coupling
# app/lead/services.py
from app.user.crud import user_crud  # ❌ Direct cross-module import in service
```

#### Module-Internal Dependencies

For dependencies within the same module (e.g., one service needs another service from the same domain), also use `dependencies.py`:

```python
# app/lead/dependencies.py
from app.lead.crud import lead_crud
from app.lead.services.lead_service import LeadService
from app.lead.services.lead_query_service import LeadQueryService

def get_lead_service() -> LeadService:
    return LeadService(lead_crud=lead_crud)

def get_lead_query_service() -> LeadQueryService:
    return LeadQueryService(lead_crud=lead_crud)
```

#### Testing Benefit

With this pattern, testing becomes trivial — mock at the DI boundary:

```python
# tests/test_lead_service.py
async def test_create_lead():
    mock_crud = AsyncMock(spec=LeadCRUD)
    mock_crud.get_by_email.return_value = None
    mock_crud.create.return_value = fake_lead

    service = LeadService(lead_crud=mock_crud, user_crud=mock_user_crud)
    result = await service.create_lead(mock_session, lead_data, current_user)

    assert result == fake_lead
    mock_crud.create.assert_called_once()
```

### 2.9 Error Handling

```python
# app/<feature>/exceptions.py
from fastapi import HTTPException, status

class LeadNotFoundError(HTTPException):
    def __init__(self, lead_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
```

- Define domain exceptions in each module's `exceptions.py`
- Never raise raw `HTTPException(status_code=500)` from services
- Global handlers in `app/core/exceptions.py` catch unhandled exceptions

### 2.12 Background Tasks (Celery)

- Define tasks in `app/<feature>/tasks.py`
- Use `app.core.background.internals.session.get_async_session` for DB access — NOT the FastAPI `get_session` dependency
- Register scheduled tasks in `app/core/background/celery_app.py` beat schedule
- Tasks are auto-discovered from all `tasks.py` files

### 2.13 Caching

```python
from app.core.cache.cache import cache

await cache.set("key", {"data": "value"}, ttl=3600)
value = await cache.get("key")
await cache.delete("key")
```

### 2.14 Configuration

- All config via `app/core/settings.py` (Pydantic BaseSettings)
- Secrets loaded from environment variables — never hardcoded
- Access via `from app.core.settings import settings`
- Computed properties for derived URLs (database_url, redis_url)

---

## 3. Frontend Architecture (Next.js)

### 3.1 Tech Stack

| Concern | Default |
|---------|---------|
| Framework | Next.js (App Router) |
| Server State | React Query (TanStack Query) |
| Client State | Zustand |
| Styling | Tailwind CSS |
| Forms | React Hook Form + Zod |
| Testing | Vitest + Playwright |
| API Mocking | MSW |

### 3.2 Project Structure

```
src/
├── app/                           # Router (Next.js App Router)
│   ├── (auth)/                    # Unauthenticated pages
│   ├── (dashboard)/               # Authenticated dashboards
│   │   └── <role>/                # One folder per user role
│   │       ├── config.ts          # Nav items, route constants — NO JSX
│   │       ├── layout.tsx         # Role layout wrapper
│   │       ├── page.tsx           # Overview page
│   │       └── <feature>/page.tsx
│   ├── api/                       # Route handlers (BFF layer)
│   ├── globals.css                # Design tokens (single source of truth)
│   ├── layout.tsx                 # Root layout — provider stack
│   └── page.tsx                   # Root redirect
│
├── components/
│   ├── layout/                    # Shell (sidebar, top nav, mobile dock)
│   ├── providers/                 # Context providers — no visual output
│   ├── shared/                    # Reusable feature components
│   │   ├── index.ts               # Barrel exports
│   │   └── <name>/index.tsx
│   └── ui/                        # Primitives (Button, Badge, Input, Dialog)
│
├── hooks/                         # App-wide custom hooks
│
├── lib/                           # Business logic — DOMAIN-BASED
│   ├── api-client.ts              # Singleton HTTP client (stateless, no stored tokens)
│   ├── <domain>/                  # One folder per business domain
│   │   ├── types.ts               # Backend* (snake_case) + Frontend (camelCase) types
│   │   ├── transformers.ts        # snake_case ↔ camelCase converters
│   │   ├── api.ts                 # Service functions → apiClient → transform → return
│   │   ├── hooks.ts               # React Query hooks (useQuery / useMutation)
│   │   ├── store.ts               # Zustand — ONLY for shared UI state (optional)
│   │   └── index.ts               # Barrel exports
│   └── utils/                     # Pure utilities (cn, formatDate, etc.)
│
├── middleware.ts                   # Route protection + API auth injection
└── types/                         # Global enums & shared interfaces
```

### 3.3 Domain Folder Rules

Every domain (`lib/<domain>/`) follows this template **exactly**:

| File | Content | Rule |
|------|---------|------|
| `types.ts` | `BackendLead` (snake_case) + `Lead` (camelCase) | Backend types use `Backend*` prefix |
| `transformers.ts` | `transformLead(raw) → Lead` | **Only place** backend field names appear |
| `api.ts` | `fetchLeads(params) → LeadListResult` | Always returns frontend types, never raw backend |
| `hooks.ts` | `useLeads()`, `useCreateLead()` | Query key factory per domain. Set `staleTime` deliberately |
| `store.ts` | UI-only state (`selectedTab`, `isOpen`) | **Optional.** NEVER `isLoading`, `error`, `items[]`, `fetchX()` |
| `index.ts` | Barrel — export only what others need | Keep it tight |

### 3.4 Transform at the Boundary

Components **never** see backend shapes. All snake_case → camelCase conversion happens once, in `transformers.ts`:

```typescript
// lib/leads/transformers.ts
export function transformLead(raw: BackendLead): Lead {
  return {
    id: raw.id,
    leadName: raw.lead_name,
    createdAt: raw.created_at,
    assignedUserId: raw.assigned_user_id,
  };
}
```

Never use auto-mappers. Always manual mapping.

### 3.5 State Management Decision Tree

```
Does this data come from an API?
├─ YES → Is it initial page load with no interactivity?
│   ├─ YES → Server Component (RSC) — async/await, no JS shipped
│   └─ NO  → React Query (client-side cache, refetch, pagination)
└─ NO  → Shared across unrelated components?
    ├─ YES → Zustand store
    └─ NO  → useState
```

**CRITICAL ANTI-PATTERN — NEVER put API data in Zustand:**

```typescript
// WRONG — re-implementing React Query inside Zustand
const useLeadStore = create((set) => ({
  leads: [],
  isLoading: false,
  error: null,
  fetchLeads: async (params) => { /* ... */ },
}));

// RIGHT — Zustand holds ONLY UI state
const useLeadUIStore = create((set) => ({
  selectedTab: "all",
  isSlideOverOpen: false,
  setSelectedTab: (tab) => set({ selectedTab: tab }),
}));

// API data lives in React Query:
const { data, isLoading } = useLeads(params);
```

### 3.6 React Query Hook Pattern

Use this exact structure per domain:

```typescript
// lib/leads/hooks.ts
export const leadKeys = {
  all: ["leads"] as const,
  lists: () => [...leadKeys.all, "list"] as const,
  list: (params) => [...leadKeys.lists(), params] as const,
  details: () => [...leadKeys.all, "detail"] as const,
  detail: (id) => [...leadKeys.details(), id] as const,
};

export function useLeads(params, options?) {
  return useQuery({
    queryKey: leadKeys.list(params),
    queryFn: () => leadService.fetchLeads(params),
    staleTime: 30_000,
    ...options,
  });
}

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: leadService.createLead,
    onSuccess: () => qc.invalidateQueries({ queryKey: leadKeys.lists() }),
  });
}
```

### 3.7 Server Components & Hydration

```typescript
// app/(dashboard)/admin/leads/page.tsx — Server Component
export default async function LeadsPage() {
  const initialData = await fetchLeads({ page: 1, limit: 50 });
  return <LeadTable initialData={initialData} />;
}

// lead-table.tsx — "use client"
export function LeadTable({ initialData }) {
  const { data } = useLeads({ page: 1 }, { initialData });
  return <DataTable data={data?.items ?? []} />;
}
```

**Mutation rule of thumb:**
- Needs optimistic UI or updates shared client cache → React Query mutation
- Simple form submit with no shared cache → Server Action
- **Never** both for the same operation

### 3.8 API Layer Flow

```
Component → Hook (hooks.ts) → Service (api.ts) → apiClient (api-client.ts) → Backend
```

- All requests go through `apiClient`. No direct `fetch()` in components.
- `apiClient` is stateless — never stores tokens. Auth handled by middleware.
- Throw `AppError` for all non-OK responses.
- On 401: refresh token → retry once → redirect to `/login` on second 401.

### 3.9 Component Rules

| Directory | Purpose |
|-----------|---------|
| `components/layout/` | Shell layout (sidebar, topnav) |
| `components/providers/` | Context wrappers — no visual output |
| `components/shared/` | Reusable feature components — import via barrel |
| `components/ui/` | Primitives — no business logic |

**Size limits:**

| Type | Max lines | If exceeded |
|------|-----------|-------------|
| Page component | ~200 | Extract sub-components or custom hooks |
| Shared component | ~150 | Extract sub-components into same folder |
| Custom hook | ~80 | Split into smaller hooks |
| Zustand store | ~50 | You're probably storing server state |

One component per folder, kebab-case folder name, `index.tsx` main file.

### 3.10 Error Handling

```typescript
class AppError extends Error {
  statusCode: number;  // 400, 401, 403, 422, 500
  message: string;     // Human-readable — safe to show in toast
  detail: unknown;     // Backend structured detail (field-level validation)
  data: unknown;       // Full raw response body
}
```

- All API errors are `AppError` instances — thrown by `apiClient`.
- Map 422 responses to individual form field errors via `err.detail`.
- Use `onError` callback in mutations, not try/catch in components.
- Root `<ErrorBoundary>` for unhandled render errors.

### 3.11 Authentication

- HTTP-only cookies — JS never reads tokens.
- Middleware injects `Authorization` header for `/api/v1/*` requests.
- Auth store (Zustand) holds user object — valid because it's session state, not server data.

### 3.12 Styling

- All tokens in `globals.css` — colors, spacing, radii, shadows, fonts.
- Use semantic tokens: `text-primary`, `bg-muted`. **Never** `text-gray-700`, `bg-[#f5f5f5]`.
- Fonts loaded once in root layout. Never import fonts in component files.
- Animations < 300ms.

### 3.13 TypeScript Rules

- No `any` without `eslint-disable` + explaining comment.
- Type all params and return types.
- Use `@/` path aliases. No relative imports beyond `../`.
- Use `export type` for type-only exports.
- Prefer string unions for small sets. Use enums when backend sends matching values.

### 3.14 Forms

- Schema = single source of truth for validation + TypeScript types.
- Keep form state local. Never in Zustand.
- Define schemas in the domain folder alongside types.

### 3.15 Performance

- Lazy-load heavy components (`ssr: false`, skeleton fallback).
- Set `staleTime` on queries (not 0).
- Virtualize long lists (> 100 rows).
- Debounce search inputs (300ms+).
- Use `React.memo` only when profiling shows re-render issues.

### 3.16 Provider Order (Root Layout)

```
ErrorBoundary > QueryClientProvider > ThemeProvider > AuthProvider > ToastProvider > ConfirmDialogProvider > {children}
```

Only truly global providers in root layout. Feature-specific providers in feature `layout.tsx`.

### 3.17 Config Files (Per Role)

Each role folder has `config.ts` — **pure data, zero JSX, zero hooks:**

- `navItems` array for sidebar
- `ROUTES` constants for all URLs (use functions for dynamic routes)
- Optional theme constants

---

## 4. Shared Rules

### 4.1 Git & Version Control

- Write descriptive commit messages: `feat: add lead creation endpoint with RBAC`
- One feature per branch, one PR per feature
- Never commit `.env`, credentials, or secrets

### 4.2 Environment Configuration

- All secrets via environment variables
- Never hardcode API URLs, keys, or credentials
- Use `.env.example` as documentation of required variables

### 4.3 API Contract

- Backend returns `snake_case` JSON
- Frontend consumes `camelCase` — transformation happens in `transformers.ts`
- Backend Pydantic schemas are the source of truth for API shape
- Frontend `Backend*` types mirror backend schemas exactly

### 4.4 When Generating Multiple Files

Always generate files in dependency order:
1. Types/schemas/models first
2. Data access (CRUD / API services) second
3. Business logic (services / hooks) third
4. **`dependencies.py`** — wiring layer (after services, before routes)
5. UI/routes last

---

## 5. Hard Don'ts (Global)

### Backend
- NO business logic in routes
- NO `session.commit()` in CRUD layer
- NO raw `HTTPException(500)` from services
- NO `datetime.utcnow()` — use `datetime.now(timezone.utc)`
- NO hardcoded secrets or config values
- NO direct SQL strings — always use SQLAlchemy ORM/Core
- NO skipping the service layer (route → CRUD directly)
- NO putting project-specific code in `app/core/`
- NO forgetting to register models in `alembic_models_import.py`
- NO forgetting to register routers in `app/apis/v1.py`
- NO cross-module imports in services — cross-module wiring belongs in `dependencies.py` only
- NO instantiating services directly in routes — always use `Depends(get_<name>_service)`
- NO importing CRUD singletons directly in service files — inject via constructor
- NO creating a module without `dependencies.py` — it is required for every feature module

### Frontend
- NO API data in Zustand (`isLoading`, `error`, `items[]`, `fetchX()`)
- NO direct `fetch()` in components
- NO hex colors / `rgba()` in component files — use design tokens
- NO silent error swallowing
- NO domain files scattered across layer folders
- NO tokens stored in `apiClient` singleton
- NO deep relative imports (`../../..`) — use `@/` aliases
- NO `any` without explanation
- NO JSX or hooks in `config.ts`
- NO raw hardcoded role strings
- NO mixing Server Actions + React Query mutations for the same operation
- NO backend `snake_case` fields leaking into components

### Both
- NO files exceeding 200 lines without extraction
- NO generating code without reading existing code first
- NO adding features, refactoring, or "improvements" beyond what was asked
- NO creating documentation files unless explicitly requested
- NO over-engineering for hypothetical future requirements

---

## 6. New Feature Checklists

### 6.1 Backend — New Feature Module

```
□ Create app/<feature>/ with __init__.py
□ Define schemas in schemas.py (Create, Update, Response)
□ Define ORM model in models.py
□ Register model import in app/core/alembic_models_import.py
□ Generate migration: alembic revision --autogenerate -m "<desc>"
□ Apply migration: alembic upgrade head
□ Implement CRUD in crud.py (extend CRUDBase)
□ Implement service in services.py (receives CRUD via constructor, owns commit)
□ Create dependencies.py (wire CRUD into service, declare cross-module deps)
□ Define domain exceptions in exceptions.py
□ Add permissions in app/user/seed.py (PERMISSIONS + ROLE_PERMISSIONS)
□ Run seed: python -m app.user.seed
□ Define routes in routes.py (inject service via Depends(get_<name>_service))
□ Register router in app/apis/v1.py
□ Export public API in __init__.py
□ Write tests
```

### 6.2 Frontend — New Domain Module

```
□ Create lib/<domain>/ folder
□ Define types.ts (Backend* snake_case + Frontend camelCase types)
□ Implement transformers.ts (manual mapping, never auto-mappers)
□ Implement api.ts (service functions → apiClient → transform → return)
□ Implement hooks.ts (query key factory + useQuery/useMutation)
□ Create store.ts ONLY if shared UI state needed (never API data)
□ Create index.ts barrel exports
□ Create page at app/(dashboard)/<role>/<feature>/page.tsx
□ Add nav item + route constant to role's config.ts
□ Import shared components from barrel — don't re-implement
□ Register heavy components in shared/lazy.tsx
□ Export new shared components through barrel
```

---

## Quick Reference — Layer Responsibility Matrix

| Action | Backend Layer | Frontend Layer |
|--------|--------------|----------------|
| Parse HTTP input | Route | — |
| Call API | — | hooks.ts → api.ts → apiClient |
| Transform data | Pydantic schema (auto) | transformers.ts (manual) |
| Business logic | Service | — (backend owns logic) |
| DB operations | CRUD (no commit) | — |
| Transaction control | Service (commit/rollback) | — |
| Dependency wiring | dependencies.py (CRUD→Service, cross-module) | — |
| DI into routes | `Depends(get_<name>_service)` | — |
| Cache API data | — | React Query |
| UI-only state | — | Zustand (no API data) |
| Auth guard | `Depends(require_permission())` | middleware.ts |
| Error handling | exceptions.py per module | AppError + onError callbacks |
| Background work | Celery tasks.py | — |
