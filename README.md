# FastAPI Backend Template

A production-ready, reusable FastAPI backend template with:

- ⚡ **FastAPI** + **SQLAlchemy 2.0** async ORM
- 🔐 **JWT auth** with refresh tokens and **RBAC** (Role-Based Access Control)
- 🗄️ **PostgreSQL** (asyncpg) + **Redis** (caching + Celery broker)
- ⚙️ **Celery** background tasks with **Flower** monitoring
- 📦 **Object storage** abstraction (DigitalOcean Spaces / S3-compatible)
- 🔄 **Alembic** async migrations
- 📊 **Prometheus** metrics via `/metrics`
- 🪵 Rotating file + colored console **logging**
- 🐳 **Docker Compose** ready (multi-stage Dockerfile)
- 📓 **Activity log** (append-only audit trail)
- 🗒️ **Release notes** (What's New system)

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
cp .env.example .env
# Edit .env — at minimum set:
#   APP_NAME, POSTGRES_*, SECRET_KEY, JWT_SECRET_KEY
```

### 2. Install Dependencies

```bash
pip install uv
uv pip install -r pyproject.toml
```

### 3. Start Infrastructure (Docker)

```bash
docker-compose up -d postgres redis
```

### 4. Run Migrations

```bash
alembic upgrade head
```

### 5. Seed Database (roles + permissions)

```bash
python -m app.user.seed
```

> **Note:** Seeding also runs automatically at startup. It is idempotent.

### 6. Create Super Admin

```bash
python -m app.user.create_admin
```

### 7. Start Application

```bash
# Development (with hot reload)
uvicorn app.core.main:app --reload

# With Docker (all services)
docker-compose up -d
```

### 8. Access API

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/health | Health check |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:5555 | Flower (Celery monitoring) |

---

## 🐳 Docker

```bash
# Start all services
docker-compose up -d

# View API logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: destroys data)
docker-compose down -v
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI application |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis (cache + Celery broker) |
| `celery_worker` | — | Background task worker |
| `flower` | 5555 | Celery task monitoring UI |

---

## ⚡ Celery (Background Tasks)

```bash
# Start worker locally (without Docker)
celery -A app.core.background.celery_app:celery_app worker --loglevel=info

# Flower monitoring locally
celery -A app.core.background.celery_app:celery_app flower --port=5555
```

---

## 📁 Project Structure

```
app/
├── core/                    # Shared infrastructure (never project-specific)
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── settings.py          # Pydantic Settings (env-based config)
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── models.py            # DeclarativeBase for all models
│   ├── crud.py              # Generic CRUDBase[Model, Create, Update]
│   ├── exceptions.py        # Global exception handlers
│   ├── middleware.py        # CORS, GZip, TrustedHost, timing
│   ├── logging.py           # Rotating + colored console logging
│   ├── metrics.py           # Prometheus instrumentator
│   ├── utils.py             # utc_now() and shared helpers
│   ├── alembic_models_import.py  # Single place to register all models
│   ├── background/          # Celery app + task infrastructure
│   ├── cache/               # Redis cache abstraction
│   └── object_storage/      # S3-compatible file storage
│
├── apis/
│   └── v1.py                # Aggregates all module routers
│
├── user/                    # Auth + RBAC module
│   ├── models.py            # User, Role, Permission, RefreshToken
│   ├── seed.py              # Idempotent role/permission seeder ← edit this
│   ├── create_admin.py      # Interactive super-admin creation CLI
│   ├── auth_management/     # JWT login, refresh, logout
│   ├── permission_management/  # RBAC scoped access helpers
│   ├── crud/                # CRUD for users, roles, permissions, tokens
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   └── routes/              # FastAPI routers
│
├── activity/                # Append-only audit log module
├── release_notes/           # "What's New" release notes module
│
└── <your_module>/           # Add new feature modules here
    ├── models/              # SQLAlchemy models
    ├── schemas/             # Pydantic schemas
    ├── crud/                # CRUD operations
    ├── services/            # Business logic
    ├── routes/              # FastAPI routers
    ├── dependencies.py      # FastAPI Depends() helpers
    ├── exceptions.py        # Module-specific exceptions
    ├── enums.py             # Module enums
    └── permissions.py       # Permission constants

migrations/                  # Alembic migration files
docker/                      # Dockerfile + entrypoint scripts
```

---

## 🏛️ Engineering Conventions

> Full standards: [engineering.hybridinteractive.in/standards/project-structure](https://engineering.hybridinteractive.in/standards/project-structure/)

This project follows the **Hybrid Interactive Engineering Standards** — a Modular Monolith architecture based on Domain-Driven Design (DDD). Files are grouped by **feature/domain** (e.g., `user/`, `product/`), not by technical concern (not all models in one folder, all routes in another).

---

### 1. Architectural Philosophy

| Principle | What It Means Here |
|-----------|-------------------|
| **Separation of Concerns** | HTTP routing, business logic, and database access are strictly decoupled into independent layers |
| **Dependency Injection** | Use FastAPI `Depends()` to pass sessions, user context, and config — never import them directly in routes |
| **Async First** | All I/O operations (DB, HTTP, file) must use `async/await` |
| **Strict Typing** | All inputs/outputs use Pydantic schemas with explicit validation — no raw `dict` returns |

---

### 2. Feature Module Structure

Every domain feature lives in its own vertical slice:

```
app/<feature_name>/
├── __init__.py          # Module public API — exports only what consumers need
├── models/              # ORM entity classes defining database tables
├── schemas/             # Pydantic models for request validation & response shaping
├── crud/                # Repository layer — exclusively DB interactions
├── services/            # Business logic — orchestrates crud, cache, external calls
├── routes/              # FastAPI routers — HTTP interface only
├── dependencies.py      # Feature-specific FastAPI Depends() providers
├── enums.py             # Feature-level enums and constants
├── exceptions.py        # Domain-specific error classes
├── tasks.py             # Celery background tasks (if applicable)
└── tests/               # Unit and integration tests for this feature
```

---

### 3. Layer Responsibilities & Strict Rules

#### A. Route Layer (`routes/`)
- **Purpose:** Parse HTTP inputs → call service → return HTTP response
- ❌ **NO business logic** — no loops, conditionals, or rule validations
- ❌ **NO direct DB queries** — never import or call `session.execute()` directly
- ✅ Rely entirely on `Depends()` for services and DB session
- ✅ Catch domain exceptions raised by services and map them to HTTP status codes

```python
# ✅ Correct route
@router.post("/leads", response_model=LeadResponse)
async def create_lead(
    data: LeadCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(require_permission("leads:create")),
):
    return await lead_service.create(session, data, created_by=current_user)
```

#### B. Service Layer (`services/`)
- **Purpose:** Execute business rules, coordinate between crud/cache/external systems
- ✅ **Owns transaction boundaries** — only services call `session.commit()` or `session.rollback()`
- ❌ Must be completely agnostic to HTTP — no `Request` or `Response` objects here
- ✅ Interacts with the DB exclusively through the module's `crud/` instances

```python
# ✅ Correct service — owns commit
async def create(self, session: AsyncSession, data: LeadCreate, created_by: User) -> Lead:
    lead = await lead_crud.create(session, obj_in=data)
    await session.commit()   # ← service owns this, always
    return lead
```

#### C. Data Access Layer (`crud/`)
- **Purpose:** Encapsulate SQL queries behind clean Python interfaces
- ✅ Inherit from `app/core/crud.py`'s `CRUDBase` wherever possible
- ❌ **NEVER call `session.commit()`** — only `session.add()` and `session.flush()`
- ✅ Methods are purely data-centric — no business conditions or rules

```python
# ✅ Correct CRUD — flush only, no commit
async def create(self, session: AsyncSession, *, obj_in: LeadCreate) -> Lead:
    db_obj = Lead(**obj_in.model_dump())
    session.add(db_obj)
    await session.flush()       # ← get DB-generated ID, never commit
    await session.refresh(db_obj)
    return db_obj
```

#### D. Schema Layer (`schemas/`)
- **Purpose:** Define structured request/response validation
- ✅ **Split by intent**: `LeadCreate`, `LeadUpdate`, `LeadResponse` — separate classes
- ✅ Enforce validation rules (string lengths, regex, value bounds) at schema level
- ❌ Never return raw ORM objects from routes — always use a `Response` schema

---

### 4. Implementing a New Feature — Execution Order

Follow this exact sequence (from the engineering standard):

```
1. schemas/   → Define request, update, and response Pydantic models
2. models/    → Define the SQLAlchemy ORM model and run migration
3. crud/      → Implement data access methods (extend CRUDBase)
4. services/  → Write business logic, call crud, commit transactions
5. routes/    → Expose HTTP endpoints, inject dependencies, use schemas
6. tests/     → Write tests covering the new behavior
```

---

### 5. Error Handling Rules

- ❌ **Never** raise a raw `HTTPException(status_code=500)` from inside services or CRUD
- ✅ Define domain exceptions in the module's `exceptions.py`:

```python
# app/product/exceptions.py
from fastapi import HTTPException, status

class ProductNotFoundException(HTTPException):
    def __init__(self, product_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found"
        )
```

- ✅ Global exception handlers in `app/core/exceptions.py` translate unhandled exceptions to safe HTTP responses
- ✅ Routes may catch domain exceptions and re-raise or return appropriate responses

---

### 6. Adding a New Feature Module — Checklist

```
□ 1. Create app/<feature>/ with the standard sub-structure
□ 2. Define schemas first  →  app/<feature>/schemas/
□ 3. Add ORM model        →  app/<feature>/models/
□ 4. Register model       →  app/core/alembic_models_import.py
□ 5. Run migration        →  alembic revision --autogenerate -m "<description>"
□ 6. Apply migration      →  alembic upgrade head
□ 7. Implement CRUD       →  app/<feature>/crud/  (extend CRUDBase)
□ 8. Implement service    →  app/<feature>/services/
□ 9. Add permissions      →  app/user/seed.py  (PERMISSIONS + ROLE_PERMISSIONS)
□ 10. Define routes       →  app/<feature>/routes/
□ 11. Register router     →  app/apis/v1.py
□ 12. Write tests         →  app/<feature>/tests/
```

See [docs/PROJECT_CONVENTIONS.md](docs/PROJECT_CONVENTIONS.md) for the full in-depth guide.

---

## 📝 Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register user |
| `POST` | `/api/v1/auth/login` | Login (returns access + refresh tokens) |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Logout (revoke refresh token) |
| `GET`  | `/api/v1/auth/me` | Get current user |
| `PUT`  | `/api/v1/auth/me` | Update profile |

---

## ⚙️ Configuration Reference

All configuration is via environment variables (`.env` file). Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_NAME` | No | Application name (default: MyApp) |
| `POSTGRES_USER` | **Yes** | Database username |
| `POSTGRES_PASSWORD` | **Yes** | Database password |
| `POSTGRES_DB` | **Yes** | Database name |
| `SECRET_KEY` | **Yes** | Min 32 chars — for signing |
| `JWT_SECRET_KEY` | **Yes** | Min 32 chars — for JWT tokens |
| `REDIS_HOST` | No | Redis host (default: localhost) |
| `ENVIRONMENT` | No | development/staging/production |

See `.env.example` for the full list.
