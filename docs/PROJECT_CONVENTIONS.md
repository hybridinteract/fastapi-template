# FastAPI Backend Project Conventions

> Extracted from `salescrm_backend` — a battle-tested reference implementation.
> Use this as the authoritative guide when starting or scaling any FastAPI + SQLAlchemy project.

---

## 1. Project Structure

```
<project_name>/
├── app/
│   ├── __init__.py
│   ├── core/                        # ✅ Reusable — never project-specific
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory + lifespan
│   │   ├── settings.py              # Pydantic BaseSettings configuration
│   │   ├── database.py              # Async SQLAlchemy engine + session
│   │   ├── models.py                # Base declarative class
│   │   ├── crud.py                  # Generic CRUDBase[Model, Create, Update]
│   │   ├── exceptions.py            # Global exception handlers
│   │   ├── middleware.py            # CORS, GZip, TrustedHost, timing
│   │   ├── logging.py               # Rotating file + colored console logging
│   │   ├── metrics.py               # Prometheus instrumentator
│   │   ├── utils.py                 # utc_now() and other shared helpers
│   │   ├── alembic_models_import.py # Single file to import all models for Alembic
│   │   ├── background/              # Celery app + task infrastructure
│   │   │   ├── celery_app.py
│   │   │   ├── tasks.py
│   │   │   └── internals/           # Base task, context, retry, monitoring
│   │   ├── cache/                   # Redis cache abstraction
│   │   │   └── cache.py
│   │   └── object_storage/          # S3-compatible file storage
│   │       ├── storage.py
│   │       └── utils.py
│   │
│   ├── apis/
│   │   └── v1.py                    # Aggregates all module routers
│   │
│   ├── user/                        # ✅ Reusable — auth + RBAC
│   │   ├── __init__.py
│   │   ├── models.py                # User, Role, Permission, RefreshToken
│   │   ├── exceptions.py
│   │   ├── seed.py                  # Idempotent role/permission seeder
│   │   ├── create_admin.py          # Interactive super-admin CLI
│   │   ├── auth_management/         # JWT login, refresh, logout
│   │   ├── permission_management/   # RBAC scoped access helpers
│   │   ├── crud/                    # user_crud, role_crud, permission_crud, refresh_token_crud
│   │   ├── schemas/                 # user_schemas, admin_schemas
│   │   ├── services/                # user_service, admin_service, user_query_service
│   │   └── routes/                  # user_routes, admin_routes
│   │
│   ├── activity/                    # ✅ Reusable — append-only audit log
│   │   ├── models.py
│   │   ├── routes.py
│   │   ├── service.py
│   │   └── crud.py
│   │
│   ├── release_notes/               # ✅ Reusable — What's New system
│   │   ├── models.py
│   │   ├── routes.py
│   │   ├── service.py
│   │   └── crud.py
│   │
│   └── <feature>/                   # 🔧 Project-specific feature modules
│       ├── __init__.py              # Module public API
│       ├── models/                  # DB models (sub-package if complex)
│       ├── schemas/                 # Pydantic schemas (sub-package if complex)
│       ├── crud/                    # CRUD classes (sub-package if complex)
│       ├── services/                # Business logic (sub-package if complex)
│       ├── routes/                  # FastAPI routers (sub-package if complex)
│       ├── dependencies.py          # FastAPI Depends() helpers
│       ├── exceptions.py            # Module-specific exceptions
│       ├── enums.py                 # Module-specific enums
│       ├── permissions.py           # Permission constants for the module
│       └── tasks.py                 # Celery tasks for the module
│
├── migrations/
│   ├── env.py                       # Alembic async env config
│   ├── script.py.mako
│   └── versions/                   # Timestamped migration files
│
├── docker/
│   ├── Dockerfile                   # Multi-stage Python build
│   ├── docker-entrypoint.sh
│   ├── celery-worker-entrypoint.sh
│   └── flower-entrypoint.sh
│
├── docs/                            # Module-level documentation
├── logs/                            # Runtime log files (gitignored)
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 2. Naming Conventions

### Files & Directories
| Type | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case.py` | `user_crud.py`, `admin_service.py` |
| Module directories | `snake_case/` | `app/lead/`, `app/release_notes/` |
| Migration files | `YYYY_MM_DD_HHMM-<rev>_<slug>.py` | `2026_02_09_0657-8600ba4ec5f7_user_init_models.py` |
| Docker scripts | `kebab-case.sh` | `celery-worker-entrypoint.sh` |

### Python Identifiers
| Type | Convention | Example |
|------|-----------|---------|
| Classes | `PascalCase` | `UserService`, `LeadCRUD` |
| Functions/methods | `snake_case` | `get_current_user`, `create_lead` |
| Constants | `UPPER_SNAKE_CASE` | `ROLES`, `PERMISSIONS`, `API_V1_PREFIX` |
| Pydantic models | `PascalCase` with suffix | `UserCreate`, `UserUpdate`, `UserResponse` |
| CRUD instances | `<model>_crud` | `user_crud`, `role_crud` |
| Service instances | `<service_name>_service` | `user_service`, `lead_service` |
| Router instances | `<module>_router` | `auth_router`, `user_router`, `lead_router` |

### Database
| Type | Convention | Example |
|------|-----------|---------|
| Table names | `plural_snake_case` | `users`, `refresh_tokens`, `role_permissions` |
| Index names | `ix_<table>_<columns>` | `ix_users_status`, `ix_activity_logs_actor_id` |
| FK constraint | SQLAlchemy default | SQLAlchemy handles naming |
| Association tables | `<table1>_<table2>` | `user_roles`, `role_permissions` |
| Enum type names | Keep SQLAlchemy default | Uses class name |

### Permissions
```
<resource>:<action>          →  "leads:view"
<resource>:<action>:<scope>  →  "leads:view:all", "leads:view:team"
```

---

## 3. Architecture Patterns

### 3.1 Layered Architecture (strict — never skip layers)

```
Route (FastAPI router)
  └── Service (business logic, transaction boundary)
        └── CRUD (DB operations, no commit)
              └── Model (SQLAlchemy ORM)
```

**Rules:**
- **Routes** inject dependencies, parse request, call service, return response
- **Services** own `session.commit()` — never in CRUD or routes
- **CRUD** uses `session.flush()` + `session.refresh()` — never `commit()`
- **Models** are pure data containers — no business logic inside models

### 3.2 Transaction Ownership

```python
# ✅ Correct — service commits
async def create_user(session: AsyncSession, data: UserCreate) -> User:
    user = await user_crud.create(session, obj_in=data)
    await session.commit()          # ← service owns this
    return user

# ❌ Wrong — CRUD commits
async def create(self, session, obj_in):
    ...
    await session.commit()          # ← NEVER in CRUD
```

### 3.3 Generic CRUDBase

```python
class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):
    # Override only what's different
    async def get_by_email(self, session, email: str) -> User | None:
        ...

user_crud = UserCRUD(User)   # Module-level singleton
```

### 3.4 Module Public API (`__init__.py`)

Each module exposes only what consumers need:

```python
# app/user/__init__.py
from .models import User
from .routes import auth_router, user_router, user_management_router

__all__ = ["User", "auth_router", "user_router", "user_management_router"]
```

---

## 4. Settings & Configuration

### 4.1 Pydantic Settings Class (`app/core/settings.py`)

- Use `BaseSettings` with `.env` file support
- Group fields with section comments: `# ==================== Database Settings ====================`
- Computed values (built from other fields) use `@property`
- Required secrets have no default — will fail fast on startup:
  ```python
  SECRET_KEY: str = Field(..., description="Secret key for signing")
  ```
- Validate secrets at class level:
  ```python
  @field_validator("SECRET_KEY", "JWT_SECRET_KEY")
  @classmethod
  def validate_secret_keys(cls, v: str, info) -> str:
      if not v or len(v) < 32:
          raise ValueError(f"{info.field_name} must be at least 32 characters")
      return v
  ```
- Cache settings with `@lru_cache()` — only one instance per process

### 4.2 Environment Variables

All env vars must be documented in `.env.example`:
```bash
# ==================== Section Name ====================
VAR_NAME=default_value     # Inline comment explaining purpose
```

---

## 5. Database & Alembic

### 5.1 Model Conventions

```python
class MyModel(Base):
    __tablename__ = "plural_snake_case"
    __table_args__ = (
        Index('ix_mytable_field', 'field'),   # Always name indexes explicitly
    )

    # Primary key — always UUID
    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Timestamps — always timezone=True, always UTC
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    # Soft delete pattern
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 5.2 Alembic Model Import

`app/core/alembic_models_import.py` — the **single source of truth** for Alembic's autogenerate:

```python
# Import Base for metadata
from app.core.models import Base

# User module
from app.user.models import User, Role, Permission, RefreshToken, UserRole, RolePermission

# Add every new module here ↓
from app.activity.models import ActivityLog
from app.release_notes.models import ReleaseNote
# from app.mymodule.models import MyModel
```

`migrations/env.py` does `from app.core.alembic_models_import import *` — add models only to the import file, never directly to env.py.

### 5.3 Migration File Naming

```
YYYY_MM_DD_HHMM-<rev>_<description>.py
2026_02_09_0657-8600ba4ec5f7_user_init_models.py
```

Configured in `alembic.ini`:
```ini
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
```

---

## 6. Authentication & RBAC

### 6.1 Permission Naming

```python
PERMISSIONS: list[tuple[str, str, str]] = [
    # (resource, action, description)
    ("leads", "view",     "View lead details"),
    ("leads", "view:all", "View all leads in the system"),
    ("users", "create",   "Create new user accounts"),
]
# Permission name stored in DB: "leads:view", "leads:view:all"
```

### 6.2 Role Definition

- Roles defined as constants in `user/seed.py`
- `is_system=True` → cannot be deleted via UI
- `super_admin` role bypasses ALL permission checks in the system

### 6.3 Seed Script (`user/seed.py`)

- **Idempotent** — safe to run multiple times; only inserts missing data
- Runs automatically on application startup (`lifespan` in `main.py`)
- Can also run manually: `python -m app.user.seed`
- Use `dispose_engine=False` when called at startup (engine shared with app)
- Keeps project-specific roles/permissions ONLY in seed.py

---

## 7. API Router Registration

### `app/apis/v1.py` — The Router Registry

```python
from fastapi import APIRouter

from app.user.routes import auth_router, user_router, user_management_router
from app.activity.routes import router as activity_router
from app.release_notes.routes import router as release_notes_router
# from app.mymodule.routes import mymodule_router  ← add new modules here

router = APIRouter()

router.include_router(auth_router)
router.include_router(user_router)
router.include_router(user_management_router)
router.include_router(activity_router, prefix="/activity-logs", tags=["Activity Logs"])
router.include_router(release_notes_router)
# router.include_router(mymodule_router)
```

**Mounting prefix** is applied in `core/main.py`:
```python
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)  # /api/v1
```

---

## 8. Celery Background Tasks

### 8.1 Task Location

- Infrastructure (Celery app config, base task class): `app/core/background/`
- Module-specific tasks: `app/<module>/tasks.py`

### 8.2 Celery App Path

```python
# Always reference as:
celery -A app.core.background.celery_app:celery_app worker
# NOT: app.core.celery_app  (old path — causes import errors)
```

### 8.3 Async Tasks

Use the async-compatible session from `app/core/background/internals/session.py` — **not** the FastAPI `get_session` dependency — for Celery tasks.

---

## 9. Exception Handling

### 9.1 Module Exceptions

Each module has its own `exceptions.py` with domain-specific exceptions as `HTTPException` subclasses:

```python
# app/lead/exceptions.py
from fastapi import HTTPException, status

class LeadNotFoundException(HTTPException):
    def __init__(self, lead_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
```

### 9.2 Global Handlers

`app/core/exceptions.py` registers global handlers on the FastAPI app for:
- `RequestValidationError` → 422
- `ValidationError` (Pydantic) → 422
- `IntegrityError` (SQLAlchemy) → 409
- `OperationalError` → 503
- `SQLAlchemyError` → 500
- `ValueError` → 400
- `PermissionError` → 403
- `Exception` (catch-all) → 500

---

## 10. Logging

### 10.1 Usage

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

logger.info("User created", extra={"user_id": str(user.id)})
logger.warning("Slow query detected")
logger.error("DB write failed", exc_info=True)
```

### 10.2 Log Files

- `logs/<APP_NAME>.log` — all logs, rotating by size
- `logs/<APP_NAME>_errors.log` — errors only, rotating by size
- Console output colored in DEBUG mode

---

## 11. Docker Setup

### 11.1 Services

| Service | Image | Port |
|---------|-------|------|
| `api` | custom Dockerfile | `${API_PORT:-8000}` |
| `postgres` | `postgres:16-alpine` | `${POSTGRES_PORT:-5432}` |
| `redis` | `redis:7-alpine` | `${REDIS_PORT:-6379}` |
| `celery_worker` | custom Dockerfile | — |
| `flower` | custom Dockerfile | `${FLOWER_PORT:-5555}` |

### 11.2 Network & Volume Naming

Always prefix with project name:
```yaml
networks:
  <project>_network:
    name: <project>_network

volumes:
  <project>_postgres_data:
    name: <project>_postgres_data
```

### 11.3 Dockerfile Pattern

Multi-stage build:
- **Stage 1 (builder)**: `python:3.13-slim` + `uv pip install`
- **Stage 2 (runtime)**: `python:3.13-slim` + non-root `appuser` (uid 1000)

---

## 12. What Goes Where (Decision Guide)

| Question | Answer |
|----------|--------|
| Does this apply to every project? | `app/core/` |
| Is this authentication/user-management? | `app/user/` |
| Is this an audit trail of events? | `app/activity/` |
| Is this version change announcements? | `app/release_notes/` |
| Is this feature-specific business logic? | `app/<feature>/services/` |
| Does this define what DB rows look like? | `app/<feature>/models/` |
| Does this define the API contract shape? | `app/<feature>/schemas/` |
| Does this define who can do what? | `app/<feature>/permissions.py` + `user/seed.py` |
| Is this a background task? | `app/<feature>/tasks.py` |
| Does this define reusable FastAPI `Depends()`? | `app/<feature>/dependencies.py` |

---

## 13. Adding a New Feature Module

1. Create `app/<feature>/` directory with the standard sub-structure
2. Add models to `app/core/alembic_models_import.py`
3. Add permissions to `app/user/seed.py` (PERMISSIONS + ROLE_PERMISSIONS)
4. Register router in `app/apis/v1.py`
5. Run `alembic revision --autogenerate -m "<description>"`
6. Run `alembic upgrade head`

---

## 14. Datetime Standards

- **All datetime fields**: `DateTime(timezone=True)` — stores with timezone
- **Default**: `default=utc_now` (from `app.core.utils`)
- **Never**: `datetime.utcnow()` — deprecated; use `datetime.now(timezone.utc)`
- **Frontend handles display timezone conversion** — backend always stores UTC

---

## 15. Dependency Injection Patterns

```python
# ✅ Standard DB session dependency
async def route(session: AsyncSession = Depends(get_session)):
    ...

# ✅ Current user dependency
async def route(current_user: User = Depends(get_current_active_user)):
    ...

# ✅ Permission guard
async def route(
    _: None = Depends(require_permission("leads:view")),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    ...
```
