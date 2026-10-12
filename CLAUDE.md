# CLAUDE.md — FastAPI Backend Template

Read this before adding or changing anything. It is the **guardrail** — one line per rule, with a
link to the place that states the rule in full. It is not the spec.

> ### This file stays under 200 lines. Adding to it is the exception.
>
> **It is read in full at the start of every session, so every line costs attention on every future
> task.** A rule earns a place here only if breaking it is **expensive and silent** — auth,
> permissions, money, data loss, or a failure that passes its tests.
>
> Everything else goes in a file and gets one line here pointing at it:
> `.claude/rules/<topic>.md` for a rule that governs specific files, `docs/` for a spec, guide, plan
> or research note, `app/<module>/<module>_doc/` for one module.
> **Before you add a paragraph here, delete one.**

<!--
MAINTAINER NOTE (stripped before this file reaches the model — free to write).
This is a TEMPLATE. Downstream projects: delete rules for modules you removed, and add your own
domain rules to `.claude/rules/`, not here. Keep this file under 200 lines; `scripts/check_docs.py`
fails the build otherwise. Rationale for the budget: docs/DECISIONS.md, 9 September 2026.
-->

**This is a starter template, not a product.** `app/iam`, `app/activity` and `app/release_notes` ship
with it. `app/iam` is the reference module — copy its shape. Delete what your project does not use,
and say so in `docs/DECISIONS.md`.

Stack: FastAPI · **async SQLAlchemy 2.0** (`Mapped`/`mapped_column`) · Alembic · Pydantic v2 ·
Postgres (asyncpg) · Redis · Celery · pytest (`asyncio_mode=auto`) · uv. Modular monolith, one
package per business module.

```bash
uv run ruff check app && uv run ruff format app
uv run ty check app                      # NOT a gate — inherited diagnostics, do not bulk-fix
uv run pytest                            # fast tier, no database. The usual run.
uv run pytest -m ""                      # + integration; needs Postgres
python3 scripts/check_docs.py            # links, stamps, rule frontmatter
docker compose exec api alembic upgrade head
```

**Tests, lint and doc checks run on the host; alembic and management commands run in the container.**
Both reach the same database — [`docs/guides/local-environment.md`](docs/guides/local-environment.md).

## Where everything is written down

| Home | Owns | Reaches you |
|---|---|---|
| This file | The guardrail | Every session |
| [`.claude/rules/`](.claude/rules/) | One cross-cutting rule per file, in full | **Automatically**, when you read a file it governs |
| [`docs/PROJECT_CONVENTIONS.md`](docs/PROJECT_CONVENTIONS.md) | **How** code is built — 21 numbered sections | On demand |
| [`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) | **Where** code goes. Read before creating any module or folder | On demand |
| [`docs/README.md`](docs/README.md) | The map of everything else — guides, plans, research, decisions | On demand |
| `app/<module>/<module>_doc/` | One module. **Read the note for the module you are working on; do not preload all of them.** | On demand |

**One owner per rule.** A rule is stated in full in exactly one place; everywhere else summarises in a
sentence and links. Copies drift, then they disagree.
Before writing any `.md`: [`docs/WRITING_DOCS.md`](docs/WRITING_DOCS.md).

## 1. Module anatomy — pick the shape before writing a file
→ [`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) §6 · `/new-module` does this for you

**Every module is layered** (`Route → Service → CRUD → Model`). The shape decides whether a layer is
a *file* or a *package*. Choose once, at the start — converting later is a churn commit that touches
every layer at once.

```
1. Owns tables AND exposes routes?     no → SHARED KERNEL (concept-named files, no routes, no
                                            dependencies.py; exceptions are ValueError)
2. Two or more sub-domains that each   yes → COMPOSITE  (sub-modules, each flat or layered, with a
   own entities?                             declared rank + tests/test_module_boundary.py)
3. Will it ever hold a second entity?  yes → LAYERED    ← the default for a domain module
                                        no → FLAT       (one table, no business rules)
```

**Name the shape and the deciding step in `<module>_doc/how-it-works.md`.**

| Layer / file | Responsibility |
|---|---|
| `models` | SQLAlchemy. `Mapped` / `mapped_column`. **`models/__init__.py` must re-export every model.** |
| `schemas` | Pydantic `XCreate` / `XUpdate` / `XResponse`. |
| `crud` | `XCRUD(CRUDBase)`. Query building and writes. **Flush-only, never commits.** |
| `services` | Business logic. **Owns the transaction** — one `commit`. |
| `routes` | Thin `APIRouter`s. Permission-gated. **`routes/__init__.py` builds no aggregator.** |
| `dependencies.py` | **Required, flat.** DI wiring, and the only file that imports across modules. |
| `exceptions.py` | **Required, flat.** Named domain exceptions subclassing `HTTPException`. |
| `enums.py` · `list_params.py` · `tasks.py` | **Always flat**, never folders. |
| `<module>_doc/how-it-works.md` · `tests/` | **Required.** |

**A folder holding one file is the correct starting shape, not a smell.** In a layered module: one
sibling per entity for `models`/`schemas`/`crud`/`routes`, one per cohesive job for `services`, and
the public import surface is always the package — nobody reaches into `crud.x`.

`app/core/` is infrastructure with **zero domain knowledge**, and its subpackages keep a `README.md`
rather than a `<module>_doc/`. The bar for putting anything there is
[`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) §2 — it is higher than people assume.

## 2. The layering contract — the most important rule
→ [`.claude/rules/layering.md`](.claude/rules/layering.md) · `PROJECT_CONVENTIONS.md` §4

```
Route ──Depends()──▶ Service ──constructor──▶ CRUD ──Depends()──▶ Session
```

- **The service owns the transaction.** Exactly **one** `await session.commit()` per mutation, in the
  service. **CRUD is flush-only** — `flush()` then `refresh()`, never `commit()` or `rollback()`.
- **Routes never touch CRUD**, and never contain business logic.
- **Services never import FastAPI types**, and never import another module directly — that is
  `dependencies.py`'s job.

## 3. Registration — both fail silently
→ [`.claude/rules/models-and-migrations.md`](.claude/rules/models-and-migrations.md)

- **Every model goes in [`app/core/alembic_models_import.py`](app/core/alembic_models_import.py)** or
  autogenerate cannot see it and the table is never created. Those imports look unused; never let an
  autofixer remove them.
- **Every router goes in [`app/apis/v1.py`](app/apis/v1.py)**, and **specific prefixes register before
  wildcard ones** or the `/{id}` route swallows its siblings.

Both are covered by tests — see §8.

## 4. Dependency injection
→ [`.claude/rules/routes-and-di.md`](.claude/rules/routes-and-di.md) · `PROJECT_CONVENTIONS.md` §5, §10

- **Every dependency in a route signature is an `Annotated` alias** — `SessionDep`, `XServiceDep`,
  `RequireXDep` — declared in `dependencies.py`. Never a bare `Depends()` in a default slot.
- **Bind a query-params model as `Annotated[XListParams, Query()]`, never `Depends()`.** With
  `Depends()` on a GET, FastAPI reads the fields as a body and they vanish from the request silently.
- **Declare a return type on every route function.** Pydantic serialises on the Rust side and filters
  sensitive fields. Never `ORJSONResponse` / `UJSONResponse`.
- **`async def` only when the body awaits something.** Blocking work goes in a plain `def`, or through
  Asyncer — blocking inside `async def` stalls the event loop for everyone.

## 5. Permissions
→ [`.claude/rules/permissions.md`](.claude/rules/permissions.md) · `PROJECT_CONVENTIONS.md` §9

- **Gate every route on a permission, never a role.** `Depends(require_permission("leads:update"))`.
  A role is a bundle the client rearranges; a role check hard-codes today's bundle and breaks silently.
- **New permissions go in [`app/iam/permission_catalog.py`](app/iam/permission_catalog.py)**, and the
  seed is **additive** — it never recomputes an existing role's grants.
- **`developer_admin` bypasses every check** and is never grantable through the API.
- **Add a permission only when a route gates on it.** One that gates nothing appears on the access
  control screen looking like a control, and is not one.

## 6. Exceptions
→ `PROJECT_CONVENTIONS.md` §13

**Every module has an `exceptions.py`** of named domain exceptions subclassing `HTTPException`.
**Neither services nor routes build a raw `HTTPException(...)` inline** — including ownership 403s.
Only `app/core/exceptions.py` and the auth layer may.

## 7. New-module checklist
→ [`docs/MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) §4 first — the bar for a new module is high.

1. Scaffold to the §1 anatomy. `/new-module` does this.
2. Models → register in `app/core/alembic_models_import.py`.
3. A **reversible** migration. Apply `upgrade` **and** `downgrade` before committing. A new `SQLEnum`
   needs an explicit `CREATE TYPE`; `op.add_column` does not emit one.
4. Permissions → `app/iam/permission_catalog.py`.
5. Router → `app/apis/v1.py`, specific prefixes before wildcards.
6. `app/<module>/<module>_doc/how-it-works.md`.
7. `app/<module>/tests/` — a package with `__init__.py`. Mark DB-dependent files `integration`.
8. `uv run pytest && python3 scripts/check_docs.py`.

## 8. Anti-patterns — do NOT do these

Each line breaks the section in brackets; go there for the fix. Starred ones fail a test.

1. `commit()` or `rollback()` in `crud.py`, or more than one commit per service mutation. [§2] ★
2. A route calling CRUD directly, or holding business logic. [§2]
3. A service importing another module's service at module level, or importing FastAPI types. [§2]
4. A raw `HTTPException(...)` built in a service or route. [§6] ★
5. A model missing from `alembic_models_import.py`, **or from its own `models/__init__.py`** — both
   make the table invisible to autogenerate. [§3] ★
6. A module with no `dependencies.py`, `exceptions.py`, or `<module>_doc/how-it-works.md`. [§1] ★
6b. Starting a domain module flat "until it gets big", or a composite module with no declared rank
    and no `tests/test_module_boundary.py`. [§1]
7. Registering a `/{id}` router before a literal-prefix sibling in `app/apis/v1.py`. [§3] ★
8. `Annotated[XListParams, Depends()]` on a GET — the params silently vanish. [§4]
9. A bare `Depends()` in a default slot instead of an `Annotated` alias. [§4]
10. Blocking work inside `async def`. [§4]
11. Hard-coding a role name instead of checking a permission, or leaving a route ungated. [§5]
12. Adding a permission no route gates on. [§5]
13. A migration with no `CREATE TYPE` for a new `SQLEnum`, or one whose `downgrade` was never run. [§7]
14. Anything domain-specific in `app/core/`, or a new `utils.py` / `shared/` holding business logic.
    [`MODULE_CONVENTIONS.md`](docs/MODULE_CONVENTIONS.md) §2, §3
15. `datetime.utcnow()` — use `utc_now()` from `app.core.utils`.
16. `python-jose` or `passlib` — unmaintained. PyJWT and pwdlib.
17. `requests` for outbound HTTP — use HTTPX.
18. Bulk-fixing inherited `ty` diagnostics inside a feature change.
19. A `.claude/rules/` file with no `paths:` frontmatter — it then loads on every session. ★
20. Pasting a rule into a second file instead of linking. [`docs/WRITING_DOCS.md`](docs/WRITING_DOCS.md)
