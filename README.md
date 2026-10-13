# FastAPI Backend Template

**A template, not an application.** Nobody deploys this repository. You start a project from it,
rename it, delete what you do not need, and build your product on top. Everything you get — auth,
RBAC, background jobs, migrations, the conventions and the docs — then belongs to your project.

This README is the only file that talks about the template. Every other doc is written about
*the app*, so it stays correct after you copy it
([`docs/WRITING_DOCS.md`](docs/WRITING_DOCS.md) → Voice). Replace this README with your project's
own once you have started.

---

## What you start with

- **FastAPI** + **async SQLAlchemy 2.0** (`Mapped` / `mapped_column`) + **Alembic** + **Pydantic v2**
- **PostgreSQL** (asyncpg) and **Redis** (cache + Celery broker)
- **Auth** — JWT access + rotating refresh tokens; email/password, Google OAuth and phone OTP providers
- **RBAC** — permissions in code (`app/iam/permission_catalog.py`), roles as editable bundles
- **Celery** background tasks, **Flower** monitoring
- **Object storage** abstraction (S3-compatible — DigitalOcean Spaces, S3)
- **Prometheus** metrics at `/metrics`, rotating file + console logging
- **Activity log** (append-only audit trail) and **release notes** ("What's New") — both optional
- **Docker Compose** for local development; CI with lint, the fast tests, and a migration round-trip
- **An AI-agent setup** — `CLAUDE.md`, path-scoped rules in `.claude/rules/`, and skills

---

## Philosophy

- **A modular monolith.** One package per business module (`iam/`, `activity/`, `<your feature>/`),
  never grouped by technical concern. Modules talk to each other only through `dependencies.py`.
- **Strict layering.** `Route → Service → CRUD → Model`. Routes are thin, the service holds the
  business rules and owns the transaction (one `commit`), CRUD only flushes.
- **Conventions are enforced, not suggested.** The rules that fail *silently* when broken — a model
  autogenerate cannot see, a `commit()` in CRUD, a module missing a required file, a `/{id}` route
  swallowing its siblings — each have a test that fails instead.
- **Permissions, not roles.** Every route gates on a permission; a role is a bundle an admin rearranges
  at runtime.
- **One owner per rule.** Each rule is written in full in exactly one file; everywhere else links to
  it. Every doc carries a "Last verified against the code" date, checked by `scripts/check_docs.py`.
- **Maintained, boring dependencies.** PyJWT and pwdlib, not python-jose and passlib; HTTPX, not
  requests.

---

## Start a project from this template

### 1. Create your repository

On GitHub, **Use this template → Create a new repository**. Or clone it and keep the template as a
second remote, so you can pull its fixes later:

```bash
git clone https://github.com/hybridinteract/fastapi-template my-app
```

```bash
git -C my-app remote rename origin template
```

```bash
git -C my-app remote add origin <your-repository-url>
```

### 2. Make it yours

| Where | Change |
|---|---|
| `pyproject.toml` | `name`, `description`, and `version` back to `0.1.0` |
| `.env` (from `.env.example`) | `APP_NAME` — it also names the Docker containers, network and volumes |
| `README.md` | Replace this file with your project's README |
| `RELEASE_NOTES.md` | Start empty — the entries here are the template's history, not yours |
| `docs/DECISIONS.md` | Keep it (these are decisions you inherit) and append one: the template version you started from |

### 3. Delete what you do not use

`app/iam` is the core — keep it. `app/activity` and `app/release_notes` are optional. To remove one:
drop its router from `app/apis/v1.py` and its models from `app/core/alembic_models_import.py`,
delete the folder, and generate a migration that drops its tables. Delete the `.claude/rules/` files
for anything you removed, and record each deletion in `docs/DECISIONS.md`.

### 4. Run it

[`docs/guides/local-environment.md`](docs/guides/local-environment.md) is the full guide. In short:
tests, lint and doc checks run on the host; alembic and management commands run in the container.

```bash
cp .env.example .env
```

```bash
uv sync --all-extras --dev
```

```bash
docker compose up -d
```

```bash
docker compose exec api alembic upgrade head
```

```bash
docker compose exec api python -m app.iam.create_admin
```

The API is at <http://localhost:8000/docs>, Flower at <http://localhost:5555>. The seed (roles and
permissions) runs on every startup.

### 5. Build your first module

Read [`CLAUDE.md`](CLAUDE.md) — it is short, and it is the guardrail. Then `/new-module` (or
[`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) §6 by hand) to choose the module's shape
and scaffold it. Deploying: [`docs/guides/deployment.md`](docs/guides/deployment.md).

### 6. Pull in template fixes later

The template keeps a [`RELEASE_NOTES.md`](https://github.com/hybridinteract/fastapi-template/blob/main/RELEASE_NOTES.md)
with an **Upgrade** section per release. Read it, then merge or cherry-pick from the `template`
remote:

```bash
git fetch template
```

---

## Structure

```
app/
├── core/          # Infrastructure with zero domain knowledge — settings, database, CRUDBase,
│                  #   exception handlers, middleware, logging, cache, background, object storage
├── apis/v1.py     # Registers every module's router (literal prefixes before /{id} ones)
├── iam/           # Identity & access: auth/, user/, permission/ — the reference module
├── activity/      # Append-only audit log (optional)
├── release_notes/ # "What's New" (optional)
└── <module>/      # Your modules — shape and files: CLAUDE.md §1
migrations/        # Alembic revisions
docker/            # Dockerfile and entrypoints
docs/              # Conventions, guides, plans, research, decisions
.claude/           # Agent rules, skills and hooks
```

## Where the conventions live

| Read | For |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | The guardrail — the rules that matter most, one line each. **Start here** |
| [`docs/PROJECT_CONVENTIONS.md`](docs/PROJECT_CONVENTIONS.md) | **How** code is built |
| [`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) | **Where** code goes — read before creating a module |
| [`.claude/rules/`](.claude/rules/) | One cross-cutting rule per file; an agent loads each when it opens a file the rule governs |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | **Why** things are the way they are |
| [`docs/README.md`](docs/README.md) | The map of everything else |

Org-wide standards:
[engineering.hybridinteractive.in/standards/project-structure](https://engineering.hybridinteractive.in/standards/project-structure/)

## Checks

```bash
uv run pytest
```

```bash
python3 scripts/check_docs.py
```

```bash
uv run ruff check app
```

`uv run pytest` is the fast tier (no database), including the convention tests; `uv run pytest -m ""`
adds the integration tests and needs Postgres. When a convention test fails, fix the code, not the
test.
