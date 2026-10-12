---
paths:
  - "app/**/crud.py"
  - "app/**/crud/**"
  - "app/**/services.py"
  - "app/**/service.py"
  - "app/**/services/**"
  - "app/**/query_service.py"
  - "app/**/providers/**"
---
# Layering — the service owns the transaction

> The long version: [`docs/PROJECT_CONVENTIONS.md`](../../docs/PROJECT_CONVENTIONS.md) §4.
> Last verified against the code: 10 September 2026.

```
Route ──Depends()──▶ Service ──constructor──▶ CRUD ──Depends()──▶ Session
```

## The rules

1. **The service owns the transaction.** Exactly **one** `await session.commit()` per mutation, in the
   service. It stamps server-controlled fields, enforces guards, writes audit, returns the result.
2. **CRUD is flush-only.** `await session.flush()` to get DB-generated ids, then `refresh()`.
   **Never** `commit()` or `rollback()` in a CRUD file. Checked by
   `app/core/tests/test_layering.py`.
3. **CRUD extends `CRUDBase`** and is instantiated as a module-level singleton (`lead_crud = LeadCRUD(Lead)`).
   Query building lives here; business rules do not. **In a layered module, `crud/__init__.py`
   re-exports each CRUD class *and* its singleton** — the singleton is what `dependencies.py` wires,
   and a second instance gives the DI copy and the copy imported by tasks and tests different
   objects. The public import surface is the package: `from app.<module>.crud import lead_crud`,
   never `from app.<module>.crud.lead import lead_crud`.
4. **Services never import FastAPI types**, and never import another module's service at module level.
   Cross-module wiring is `dependencies.py`'s job — and a deferred import inside a function is the
   correct escape hatch for a genuine cycle, not a style choice.
5. **Audit is fire-and-forget, after commit.** Never inside the transaction: the dispatch is not
   transactional, so a rollback leaves a log entry for something that did not happen.
6. **Cache invalidation is after commit too.** A pre-commit bust lets a concurrent read re-cache a
   value the rollback would have erased.
7. **Never trust a `created_by` or owner id from the request body.** The service stamps it from the
   authenticated principal.

## Where it IS used

| Where | Commits | Notes |
|---|---|---|
| `app/iam/user/services.py` | 8 | The busiest service; the shape to copy |
| `app/iam/auth/services.py` | 4 | Plus 3 more in `auth/providers/` — providers are service-layer |
| `app/release_notes/service.py` | 4 | Singular `service.py`; small modules keep the flat name |
| `app/iam/permission/services.py` | 1 | |
| `app/activity/service.py` | 1 | |

CRUD files — `app/*/crud.py`, `app/iam/*/crud.py`, `app/core/crud/` — contain **zero** commits.

## Where it is deliberately NOT applied

- **`app/core/database.py`** commits in the session dependency's teardown, and
  **`app/core/background/internals/`** commits in the Celery session helpers. Those files *are* the
  transaction boundary; they are infrastructure, not a service.
- **`app/iam/auth/providers/*.py`** commit. They are service-layer despite the folder name — a
  provider is the sign-in service for one identity source.
- **`app/iam/user/query_service.py`** never commits. It is a read/cache path, not a mutation service.

## Known gaps

- No service currently uses an explicit `rollback()`; the session dependency handles it. If you add
  one, it belongs in the service, never in CRUD.
- `expire_on_commit=False` is set on the session factory (correct for async) — which means
  `selectinload` **will not overwrite an already-loaded collection**. After mutating a relationship,
  reload with `populate_existing=True` or in a fresh session, or the caller sees stale children.

## How to re-check this rule

```bash
# Every commit() call site, by file. CRUD files must not appear.
grep -rn "session.commit()" app --include="*.py" | grep -v "^app/core/"

# The layering test, which is the enforced version of rules 2 and the exceptions rule.
uv run pytest app/core/tests/test_layering.py -v
```
