# `app/core/crud` — Package Reference

This package provides the two building blocks every module needs for database access:

| Symbol | File | Purpose |
|---|---|---|
| `CRUDBase` | `base.py` | Generic async CRUD (get / create / update / remove / count / exists) |
| `apply_sorting()` | `helpers.py` | Whitelist-guarded dynamic `ORDER BY` with stable tiebreaker |
| `paginated_select()` | `helpers.py` | Single-query `count() OVER ()` pagination pattern |

All three are re-exported from `app.core.crud`:

```python
from app.core.crud import CRUDBase, apply_sorting, paginated_select
```

---

## 1. CRUDBase — Quick Reference

`CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]` provides seven
async methods. Sub-class it and override only what differs.

```python
# app/mymodule/crud/thing_crud.py
from app.core.crud import CRUDBase
from app.mymodule.models import Thing
from app.mymodule.schemas import ThingCreate, ThingUpdate

class ThingCRUD(CRUDBase[Thing, ThingCreate, ThingUpdate]):
    pass            # free CRUD for all 7 base operations

thing_crud = ThingCRUD(Thing)   # module-level singleton
```

### Methods

| Method | Signature | Notes |
|---|---|---|
| `get` | `(session, id) → Model \| None` | Returns `None` if not found |
| `get_multi` | `(session, skip, limit) → list[Model]` | No filter, no total — simple paging only |
| `create` | `(session, obj_in) → Model` | `flush()` + `refresh()` — does NOT commit |
| `update` | `(session, db_obj, obj_in) → Model` | Pydantic schema or dict — does NOT commit |
| `remove` | `(session, id) → bool` | Hard-delete — does NOT commit |
| `count` | `(session) → int` | Un-filtered table row count |
| `exists` | `(session, id) → bool` | Fast existence check by PK |

> **Rule:** CRUD methods never call `session.commit()`.  
> The Service layer owns the transaction boundary. See PROJECT_CONVENTIONS §3.2.

---

## 2. List Endpoints — The Standard Pattern

Any list endpoint that needs **filtering + sorting + pagination + total count**
should follow this five-layer recipe.

### Overview

```
Route (XxxListParams = Depends())
  └─ Service (thin pass-through + business-rule overrides)
       └─ CRUD.get_list_filtered(…)
            └─ paginated_select(session, base_query, …)
                 └─ Single SQL: SELECT …, COUNT(*) OVER () OFFSET … LIMIT …
                      └─ Returns (items, total)
```

---

### Step 1 — Enums (`app/mymodule/enums.py`)

Define a sort-field enum with exactly the column names the UI may sort by.

```python
from enum import Enum

class ThingSortField(str, Enum):
    CREATED_AT = "created_at"
    NAME       = "name"
    STATUS     = "status"

class SortDirection(str, Enum):
    ASC  = "asc"
    DESC = "desc"
```

---

### Step 2 — ListParams schema (`app/mymodule/schemas/thing_schemas.py`)

Subclass `ListParams` and override `sort_by` with the typed enum.
Add every filter field the endpoint will expose.

```python
from typing import Optional
from pydantic import Field
from app.core.schemas import ListParams
from app.mymodule.enums import ThingSortField, SortDirection

class ThingListParams(ListParams):
    # Override sort fields with typed enums so Swagger shows dropdowns
    # and FastAPI returns 422 for invalid values (instead of silent fallback).
    sort_by:    ThingSortField = ThingSortField.CREATED_AT
    sort_order: SortDirection  = SortDirection.DESC

    # Module-specific filters
    search:    Optional[str]  = None
    status:    Optional[str]  = None
    date_from: Optional[date] = None
    date_to:   Optional[date] = None
```

`ListParams` base fields (always inherited):

| Field | Default | Constraints |
|---|---|---|
| `skip` | `0` | `ge=0` |
| `limit` | `100` | `ge=1, le=500` |
| `sort_by` | `None` | `str` — overridden in subclass |
| `sort_order` | `"desc"` | `"asc" \| "desc"` — overridden in subclass |

`model_config = ConfigDict(extra="ignore")` is set on the base — unknown query
params are silently dropped, so adding new frontend params never causes 422 errors.

---

### Step 3 — CRUD method (`app/mymodule/crud/thing_crud.py`)

```python
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.crud import CRUDBase, paginated_select
from app.mymodule.models import Thing
from app.mymodule.schemas import ThingCreate, ThingUpdate

# Map sort_by string values → ORM columns (safe — no getattr on raw input)
_SORT_COL_MAP = {
    "created_at": Thing.created_at,
    "name":       Thing.name,
    "status":     Thing.status,
}

class ThingCRUD(CRUDBase[Thing, ThingCreate, ThingUpdate]):

    async def get_list_filtered(
        self,
        session: AsyncSession,
        *,
        skip: int,
        limit: int,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search: Optional[str] = None,
        status: Optional[str] = None,
        date_from=None,
        date_to=None,
        owner_user_ids: Optional[List] = None,   # scope — None means no restriction
    ) -> Tuple[List[Thing], int]:
        """Return a filtered, sorted page of Things plus the un-paginated total."""

        filters = [Thing.is_deleted.is_(False)]

        if search:
            from app.core.utils.text import escape_like
            term = f"%{escape_like(search)}%"
            filters.append(Thing.name.ilike(term))

        if status:
            filters.append(Thing.status == status)

        if date_from:
            filters.append(Thing.created_at >= date_from)
        if date_to:
            filters.append(Thing.created_at <= date_to)

        if owner_user_ids is not None:
            filters.append(Thing.assigned_to.in_(owner_user_ids))

        # Build ORDER BY — whitelist guards against arbitrary column names
        sort_col = _SORT_COL_MAP.get(sort_by, Thing.created_at)
        order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
        order_clauses = [order, Thing.id.desc()]   # tiebreaker last

        base_query = select(Thing).where(*filters)

        return await paginated_select(
            session,
            base_query,
            skip=skip,
            limit=limit,
            order_clauses=order_clauses,
        )

thing_crud = ThingCRUD(Thing)
```

---

### Step 4 — Service (`app/mymodule/services/thing_service.py`)

The service is a thin pass-through unless there are business rules on top.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.mymodule.crud.thing_crud import thing_crud
from app.mymodule.schemas import ThingListParams, ThingListResponse

class ThingService:

    async def list_things(
        self,
        session: AsyncSession,
        params: ThingListParams,
        owner_user_ids=None,
    ) -> ThingListResponse:
        items, total = await thing_crud.get_list_filtered(
            session,
            skip=params.skip,
            limit=params.limit,
            sort_by=params.sort_by.value,
            sort_order=params.sort_order.value,
            search=params.search,
            status=params.status,
            date_from=params.date_from,
            date_to=params.date_to,
            owner_user_ids=owner_user_ids,
        )
        return ThingListResponse(items=items, total=total, skip=params.skip, limit=params.limit)

thing_service = ThingService()
```

---

### Step 5 — Route (`app/mymodule/routes/thing_routes.py`)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.mymodule.schemas import ThingListParams, ThingListResponse
from app.mymodule.services.thing_service import thing_service
from app.iam.dependencies import get_current_user
from app.iam import User

router = APIRouter(prefix="/things", tags=["Things"])

@router.get("/", response_model=ThingListResponse)
async def list_things(
    params: ThingListParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Scope: if user lacks read_all permission, restrict to their own rows
    owner_user_ids = None
    if not current_user.has_permission("things:read_all"):
        owner_user_ids = [current_user.id]

    return await thing_service.list_things(session, params, owner_user_ids=owner_user_ids)
```

**What FastAPI does automatically:**
- Deserialises every query param into `ThingListParams` fields.
- Validates enum fields — `sort_by=invalid_value` returns **422** before
  any service/CRUD code runs.
- Renders enum dropdowns in Swagger UI.

---

## 3. `paginated_select()` — Reference

```python
async def paginated_select(
    session: AsyncSession,
    base_query: Select,
    *,
    skip: int,
    limit: int,
    order_clauses: Sequence[ColumnElement],
    extra_columns: Optional[Sequence[ColumnElement]] = None,
) -> Tuple[List[Any], int]:
```

**SQL emitted:**
```sql
SELECT thing.*, COUNT(*) OVER () AS _total
FROM   things
WHERE  is_deleted = false AND status = 'active'
ORDER  BY created_at DESC, id DESC
OFFSET :skip LIMIT :limit;
```

PostgreSQL evaluates the `WHERE` clause once and uses the result set for
both the `LIMIT` slice and the window-function count — **one DB round-trip**.

### `extra_columns` — for cross-JOIN queries

When the `base_query` selects the primary model **plus** additional columns
from a JOIN, declare them in `extra_columns` so `paginated_select` knows
the row layout:

```python
call_stats = (
    select(
        SalesCall.customer_id,
        func.max(SalesCall.created_at).label("last_call_time"),
        func.count(SalesCall.id).label("call_count"),
    )
    .group_by(SalesCall.customer_id)
    .subquery()
)

base_query = (
    select(Customer, call_stats.c.last_call_time, call_stats.c.call_count)
    .outerjoin(call_stats, Customer.id == call_stats.c.customer_id)
    .where(*filters)
)

items, total = await paginated_select(
    session, base_query,
    skip=skip, limit=limit,
    order_clauses=order_clauses,
    extra_columns=[call_stats.c.last_call_time, call_stats.c.call_count],
)
# Each item in `items` is a tuple: (Customer, last_call_time, call_count)
```

---

## 4. `apply_sorting()` — Reference

```python
def apply_sorting(
    query,
    model,
    sort_by: Optional[str],
    sort_order: str = "desc",
    allowed_fields: Optional[List[str]] = None,
    default_field: str = "created_at",
    default_order: str = "desc",
    tiebreaker_field: Optional[str] = "id",
) -> query:
```

Use `apply_sorting()` when you don't need a sort-column map (i.e. all
sortable columns are direct model attributes with the same name as the
sort_by string):

```python
query = apply_sorting(
    query,
    Employee,
    sort_by=params.sort_by,
    sort_order=params.sort_order,
    allowed_fields=["name", "created_at", "date_of_joining", "status"],
    default_field="created_at",
)
```

If `sort_by` is not in `allowed_fields`, it falls back to `default_field`
silently. For stricter behaviour (422 on invalid values), use a typed enum
on `XxxListParams.sort_by` instead — the rejection happens before CRUD runs.

---

## 5. Decision Guide

| Scenario | Use |
|---|---|
| Simple CRUD with no filtering | `CRUDBase` only |
| Full list endpoint with filters + total | `paginated_select()` + `ListParams` subclass |
| All sort columns are direct model fields | `apply_sorting()` |
| Sort columns include computed/joined values | Inline sort-column map dict in CRUD |
| Infinite-scroll (no total needed) | Simple `select … OFFSET LIMIT` without window |
| Soft-delete resource | Override `remove()` to set `is_deleted = True` |

For search technique selection (iLIKE vs trigram vs FTS vs hybrid), indexing
strategy, and filter+search sync rules, see
[SEARCH_STRATEGY.md](./SEARCH_STRATEGY.md).
