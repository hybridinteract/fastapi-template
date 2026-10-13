---
name: review-module
description: Review a module against the project's conventions before a PR. Use when asked to review a module, check code against the conventions, prepare a pull request, or verify a module was built correctly.
---

# Review a module

Run the mechanical checks first — they are faster than reading, and they cover the four
rules that fail silently. Then read for the things no test can see.

## 1. Mechanical

```bash
uv run pytest                                  # the four convention tests
uv run ruff check app/<module>
python3 scripts/check_docs.py
```

If a convention test fails, **fix the code, not the test.** If the rule is genuinely wrong,
change `CLAUDE.md` and add an entry to `docs/DECISIONS.md` in the same change.

`ruff` reports several hundred inherited findings repo-wide. Compare against the module you
are reviewing only, and **do not bulk-fix unrelated ones inside a feature change.**

## 2. Shape — before anything else

**Name the module's shape**, then check it was the right one and that its contract holds.
`docs/MODULE_CONVENTIONS.md` §6.

| Shape | It is right when | Check |
|---|---|---|
| **Flat** | one table, no business rules | Would a second entity ever land here? If yes it should be layered — say so now, while the conversion is small |
| **Layered** | a domain module with ≥2 entities | `models/__init__.py` re-exports **every** model · `crud/__init__.py` re-exports each class **and** its singleton · `routes/__init__.py` builds **no** aggregator · nothing imports a layer's sibling directly (`from …crud.lead import` is wrong; `from …crud import` is right) |
| **Composite** | one bounded context, ≥2 sub-domains | Root `__init__.py` exports **nothing** and declares the rank · **one** `dependencies.py`, `tests/`, `<module>_doc/` at the root · `tests/test_module_boundary.py` exists and is not weakened |
| **Shared kernel** | business primitives, no HTTP | No routes, no models, no `dependencies.py`, no migration · `exceptions.py` raises `ValueError`, not `HTTPException` · a route here means it should have been a domain module |

- **`<module>_doc/how-it-works.md` names the shape and the step that chose it.** If it does not, ask
  the author which step decided — the answer is often "nobody chose, it just grew".
- **These stay flat in every shape:** `dependencies.py`, `exceptions.py`, `enums.py`,
  `list_params.py`, `tasks.py`. A folder named for one of them is a finding.
- **A folder holding one file is not a finding.** It is the documented starting shape.

## 3. Layering — read `services.py` and `crud.py` together

- Exactly **one** `await session.commit()` per service mutation. Two means a partial write
  is possible; zero means nothing persists.
- CRUD has no `commit()` or `rollback()`. It flushes and refreshes.
- The service stamps `created_by` and any owner id **from the authenticated principal**,
  never from the request body.
- Audit logging and cache invalidation happen **after** commit, never inside the transaction.
- No cross-module import at module level in a service — that belongs in `dependencies.py`.

## 4. Routes

- Every dependency is an `Annotated` alias from `dependencies.py`. No bare `Depends()` in a
  default slot.
- A query-params model is bound `Annotated[XListParams, Query()]`. **`Depends()` here makes
  the parameters vanish silently** — check this explicitly, it is the most expensive
  mistake in the file.
- Every route function declares a return type.
- `async def` only where the body awaits. Blocking work in `async def` stalls the loop.
- Every route is permission-gated, and gated on a **permission**, never a role name.
- No raw `HTTPException(...)` — named exceptions from the module's `exceptions.py`.

## 5. Models and the migration

- Every new model is in `app/core/alembic_models_import.py`.
- Enums declared with `values_callable`.
- Timestamps use `utc_now()`, not `datetime.utcnow()`.
- Relationships load explicitly via `selectinload` in a dedicated `get_with_relations`.
- The migration's `downgrade()` has actually been run. Ask; do not assume.
- A new `SQLEnum` has an explicit `CREATE TYPE` / `DROP TYPE`.

## 6. Placement

- Nothing domain-specific landed in `app/core/`.
- No new `utils.py` / `helpers.py` / `shared/` holding business logic.
- The module earns its place — `docs/MODULE_CONVENTIONS.md` §4.

## 7. Documentation

- `app/<module>/<module>_doc/how-it-works.md` exists, has a stamp, and **describes what the
  code now does** rather than what it did when it was written.
- No loose `.md` beside the `.py` files.
- Nothing was pasted into a second file that should have been a link.
- If a convention changed, `docs/DECISIONS.md` has an entry.

## 8. Report

Say what you checked and what you found. **Quote real numbers** (`12 passed`), never "tests
pass". Name any failure that predates this change and how you know it predates it —
otherwise the next reviewer investigates it again.

List findings most-severe first, and separate "this is broken" from "I would have done this
differently".
