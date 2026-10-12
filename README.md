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
python -m app.iam.seed
```

> **Note:** Seeding also runs automatically at startup. It is idempotent.

### 6. Create Developer Admin

```bash
python -m app.iam.create_admin
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
├── iam/                     # Identity & access: auth + users + RBAC
│   ├── __init__.py          # Public API exports (routers, deps, guards)
│   ├── config.py            # AuthConfig — JWT, providers, role names
│   ├── dependencies.py      # DI wiring (CRUD → Service)
│   ├── permission_catalog.py # Roles + permission constants ← edit this
│   ├── seed.py              # Idempotent role/permission seeder ← edit this
│   ├── create_admin.py      # Interactive developer-admin creation CLI
│   ├── extensions.py        # ExtraUserFieldsMixin for project columns
│   ├── iam_doc/             # Module documentation
│   ├── auth/                # Login, refresh, logout, tokens, providers
│   ├── user/                # User accounts + admin user management
│   └── permission/          # Roles, permissions, RBAC route guards
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

A **modular monolith** built on Domain-Driven Design: files are grouped by feature
(`iam/`, `activity/`, `<your feature>/`), never by technical concern. Strict layering —
`Route → Service → CRUD → Model` — with the service owning the transaction.

The conventions are not repeated here, because a summary beside the real thing drifts from
it. Each lives in exactly one place:

| Read | For |
|---|---|
| **[`CLAUDE.md`](CLAUDE.md)** | The rules that matter most, in ~170 lines. **Start here.** AI agents load it automatically at the start of every session |
| [`docs/README.md`](docs/README.md) | The map of every other document |
| [`docs/PROJECT_CONVENTIONS.md`](docs/PROJECT_CONVENTIONS.md) | **How** code is built — 21 numbered sections |
| [`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) | **Where** code goes. Read before creating any module |
| [`.claude/rules/`](.claude/rules/) | One file per cross-cutting rule. An agent loads each one automatically when it opens a file that rule governs |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | **Why** things are the way they are |

Org-wide standards:
[engineering.hybridinteractive.in/standards/project-structure](https://engineering.hybridinteractive.in/standards/project-structure/)

### Checks

```bash
uv run pytest                    # convention tests + the fast tier
python3 scripts/check_docs.py    # links, doc freshness, rule frontmatter
uv run ruff check app            # inherited baseline — see docs/planning/modernization.md
```

Four tests enforce the rules that otherwise fail **silently**: a model missing from
`alembic_models_import.py`, a `commit()` in the CRUD layer, a module that does not match the
contract for its shape, and a router registered in an order that lets `/{id}` swallow its siblings.
When one fails, fix the code — not the test.

### Module shapes

A module is one of four shapes, chosen deliberately before the first file — **flat**, **layered**
(the default for a domain module), **composite** (sub-modules with a declared import rank), or a
**shared kernel** (business primitives, no HTTP). The decision procedure is three questions:
[`CLAUDE.md`](CLAUDE.md) §1, in full at
[`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) §6. `/new-module` walks it for you.

### Working with an AI agent

`CLAUDE.md` is loaded every session; `.claude/rules/*.md` load only when a matching file is
opened, so deep rules cost nothing until they are relevant. Three skills are available:
`/new-module`, `/new-migration`, `/review-module`.

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
