---
paths:
  - "app/**/routes.py"
  - "app/**/routes/**"
  - "app/**/dependencies.py"
  - "app/**/schemas.py"
  - "app/**/list_params.py"
  - "app/apis/**"
---
# Routes, dependency injection, and list endpoints

> The long version: [`docs/PROJECT_CONVENTIONS.md`](../../docs/PROJECT_CONVENTIONS.md) §4, §5, §10, §11.
> Last verified against the code: 10 September 2026.

## The rules

1. **Every dependency in a route signature is an `Annotated` alias** — `SessionDep`, `XServiceDep`,
   `RequireXDep` — declared in that module's `dependencies.py`. Never a bare `Depends()` sitting in a
   default slot, and never `Annotated[SomeClass, Depends()]`.
2. **Every request parameter uses `Annotated`** — `Query`, `Path`, `Header`, `Cookie`, `Form`, `File` —
   with the Python default on the right-hand side where it belongs.
3. **Bind a query-params model as `Annotated[XListParams, Query()]`, never `Depends()`.** With
   `Depends()` on a GET, FastAPI reads the model's fields as a *body*, and they vanish from the
   request with no error. This is the single most expensive mistake in this file.
4. **Declare a return type on every route function.** Pydantic serialises it on the Rust side and
   filters fields the response schema does not name. Use `response_model=` only when the annotation
   cannot express it. Never `ORJSONResponse` / `UJSONResponse` — deprecated.
5. **`async def` only when the body awaits something.** Blocking work goes in a plain `def` (FastAPI
   runs it in a threadpool) or through Asyncer. Blocking inside `async def` stalls the loop for every
   concurrent request, and nothing errors.
6. **One function per HTTP method.** No `api_route(methods=[...])`.
7. **Declare `prefix`, `tags` and shared `dependencies` on the `APIRouter` itself**, not on
   `include_router()`. The module stays self-contained and `app/apis/v1.py` stays readable.
8. **Registration order in [`app/apis/v1.py`](../../app/apis/v1.py) is load-bearing.** Literal prefixes
   register **before** wildcard ones, or `/{id}` swallows its siblings and the caller gets a UUID parse
   error about a field they never sent. Checked by `app/apis/tests/test_route_registration.py`.
9. **Routes never contain business logic and never touch CRUD.** They parse, delegate, return.
10. **Routes raise named exceptions from the module's `exceptions.py`** — including ownership 403s.
    Never a raw `HTTPException(...)`.
11. **In a layered module, `routes/__init__.py` re-exports each router and builds no aggregator.**
    `app/apis/v1.py` registers them one by one, so the registration order stays visible in the one
    file that owns it. An `__init__.py` that assembles a router at import time hides the ordering
    hazard from rule 8 inside a file nobody thinks to read — and splitting `routes.py` is exactly
    what moves that hazard out of one file's declaration order and into `v1.py`.
    `test_route_registration.py` is what keeps it caught either way.

## The list-endpoint flow

```
Route  params: Annotated[XListParams, Query()]
  └─ Service  pass-through + business-rule narrowing (scope, ownership)
       └─ CRUD.get_list_filtered(session, skip, limit, sort_by, sort_order, …filters)
```

- `XListParams(ListParams)` lives in a flat **`list_params.py`** with `sort_by: Literal[...]` naming
  the sortable columns. It is a route concern, not an entity, so it stays out of `schemas/` and that
  package can be strictly one sibling per entity. (`app/activity` predates this and still declares
  `ActivityListParams` in `schemas.py`.) **The `Literal` and the CRUD layer's `allowed_fields`
  whitelist must match** — a dynamic `ORDER BY` with no whitelist is an injection surface.
- **One `WHERE`**: filters, then search. Never post-filter in Python, and never build `ILIKE` without
  escaping `%` and `_`.
- Page with `paginated_select()`, which returns `(items, total)` in one round trip.
- **Re-declare any default that should differ from `ListParams`.** `ActivityListParams` keeps a page
  size of 50; adopting the base class without re-declaring silently changes your endpoint's contract.

## Where it IS used

| Where | What |
|---|---|
| [`app/activity/`](../../app/activity/) | **The reference implementation.** Read `schemas.py`, `crud.py`, `service.py`, `routes.py` together |
| [`app/release_notes/`](../../app/release_notes/) | The simple case — flat `Annotated[..., Query()]` params, no params model |
| [`app/iam/dependencies.py`](../../app/iam/dependencies.py) | The DI aliases every other module copies |
| [`app/apis/v1.py`](../../app/apis/v1.py) | Registration, in order |

## Where it is deliberately NOT applied

- **A list with two or three filters does not need a params model.** `release_notes` declares flat
  `Query()` parameters and is correct. Adopt `XListParams` when the signature stops fitting on a
  screen, not before.
- **`app/core/crud/helpers.py`** builds `ORDER BY` dynamically — that is the whitelisted implementation
  the rule points at, not a violation of it.

## Known gaps

- There is no repo-wide test that every `XListParams.sort_by` `Literal` matches its CRUD
  `allowed_fields`. Until there is, check it by hand when adding a sortable column.

## How to re-check this rule

```bash
# Should return nothing: a params model bound with Depends() on a route.
grep -rn "Depends()\]" app --include="routes.py"

# Should return nothing: raw HTTPException in a route or service.
uv run pytest app/core/tests/test_layering.py -v

# Router order.
uv run pytest app/apis/tests/test_route_registration.py -v
```
