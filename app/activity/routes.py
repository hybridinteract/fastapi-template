"""Activity log admin endpoints."""

from datetime import date, datetime, time, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionDep
from app.user.permission_management import require_permission
from .dependencies import ActivityServiceDep
from .enums import ActivityAction
from .schemas import ActivityLogListResponse, BulkDeleteRequest

router = APIRouter(
    prefix="/activity-logs",
    tags=["Activity Logs"],
    dependencies=[Depends(require_permission("activity:read_all"))],
)


@router.get("", summary="List activity logs")
async def list_activity_logs(
    session: SessionDep,
    service: ActivityServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    actor_id: Annotated[UUID | None, Query(description="Filter by user ID")] = None,
    actor_name: Annotated[str | None, Query(description="Search by actor name (partial match)")] = None,
    action: Annotated[ActivityAction | None, Query(description="Filter by action type")] = None,
    date_from: Annotated[date | None, Query(description="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[date | None, Query(description="End date (YYYY-MM-DD)")] = None,
) -> ActivityLogListResponse:
    """
    Retrieve a paginated list of activity logs with optional filters.

    Returns a chronologically sorted (newest first) audit trail of all
    user actions in the system. Supports filtering by user, action type,
    and date range.

    ## Query Parameters

    | Parameter | Type | Description |
    |---|---|---|
    | `skip` | int | Pagination offset (default `0`, min `0`) |
    | `limit` | int | Page size (default `50`, min `1`, max `500`) |
    | `actor_id` | UUID | Exact match — show only actions by this user |
    | `actor_name` | string | Partial match (case-insensitive) on actor name |
    | `action` | enum | Filter by action type (see below) |
    | `date_from` | date | Start date inclusive (YYYY-MM-DD) |
    | `date_to` | date | End date inclusive (YYYY-MM-DD) |

    ## Action Types

    | Action | Description |
    |---|---|
    | `CREATE` | Resource was created |
    | `UPDATE` | Resource was updated |
    | `DELETE` | Resource was soft-deleted |
    | `STATUS_CHANGE` | Resource status changed |
    | `ASSIGN` | Resource assigned to a user |
    | `IMPORT` | Resources imported via file |

    ### Standard Resource Types
    `user`, `role`, `document`, `product`, `settings`

    **Example Request Body**
    ```json
    {
      "action": "CREATE",
      "resource_type": "document",
      "resource_id": "DOC-123",
      "details": {"summary": "Created design document"},
      "ip_address": "192.168.1.100"
    }
    ```

    ## Response — `ActivityLogListResponse`
    ```json
    {
      "items": [
        {
          "id": "uuid",
          "actor_id": "uuid",
          "actor_name": "John Doe",
          "action": "CREATE",
          "resource_type": "document",
          "resource_id": "DOC-123",
          "details": {"summary": "Created design document"},
          "ip_address": "192.168.1.1",
          "created_at": "2026-02-24T10:30:00Z"
        }
      ],
      "total": 142,
      "skip": 0,
      "limit": 50
    }
    ```

    ## Permission
    Requires **`activity:read_all`** (admin only).

    ## Errors
    - **401** — Missing or invalid authentication token
    - **403** — Caller lacks `activity:read_all` permission
    - **422** — Invalid query parameter (e.g. malformed UUID, invalid date)
    """
    dt_from = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
    dt_to = datetime.combine(date_to, time.max, tzinfo=timezone.utc) if date_to else None

    return await service.list_logs(
        session,
        skip=skip,
        limit=limit,
        actor_id=actor_id,
        actor_name=actor_name,
        action=action.value if action else None,
        date_from=dt_from,
        date_to=dt_to,
    )


@router.delete("", status_code=status.HTTP_200_OK, summary="Bulk delete activity logs")
async def bulk_delete_activity_logs(
    body: BulkDeleteRequest,
    session: SessionDep,
    service: ActivityServiceDep,
) -> dict[str, int]:
    """
    Permanently delete activity logs by IDs (multi-select).

    Performs a **hard delete** — records are irrecoverably removed from the
    database. This is intended for housekeeping and compliance purposes.

    ## Request Body — `BulkDeleteRequest`

    | Field | Type | Constraints | Description |
    |---|---|---|---|
    | `ids` | UUID[] | min 1, max 200 | Activity log IDs to delete |

    ```json
    {
      "ids": [
        "550e8400-e29b-41d4-a716-446655440000",
        "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
      ]
    }
    ```

    ## Response
    ```json
    {
      "deleted": 2
    }
    ```
    Returns the count of records actually deleted. May be less than the
    number of IDs provided if some IDs were not found.

    ## Permission
    Requires **`activity:read_all`** (admin only).

    ## Errors
    - **401** — Missing or invalid authentication token
    - **403** — Caller lacks `activity:read_all` permission
    - **422** — Validation error (empty list, exceeds 200 IDs, malformed UUIDs)
    """
    deleted = await service.bulk_delete(session, body.ids)
    return {"deleted": deleted}
