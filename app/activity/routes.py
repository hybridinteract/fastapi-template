"""Activity log admin endpoints."""

from datetime import date, datetime, time, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.user.permission_management import require_permission
from .crud import activity_log_crud
from .enums import ActivityAction
from .schemas import ActivityLogListResponse, BulkDeleteRequest
from .service import ActivityLogService

router = APIRouter()

_service = ActivityLogService(crud=activity_log_crud)


def _get_service() -> ActivityLogService:
    return _service


@router.get(
    "",
    response_model=ActivityLogListResponse,
    summary="List activity logs",
    dependencies=[Depends(require_permission("activity:read_all"))],
)
async def list_activity_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    actor_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    actor_name: Optional[str] = Query(None, description="Search by actor name (partial match)"),
    action: Optional[ActivityAction] = Query(None, description="Filter by action type"),
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
    service: ActivityLogService = Depends(_get_service),
):
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
    # Convert date to datetime for range filtering
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


@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    summary="Bulk delete activity logs",
    dependencies=[Depends(require_permission("activity:read_all"))],
)
async def bulk_delete_activity_logs(
    body: BulkDeleteRequest,
    session: AsyncSession = Depends(get_session),
    service: ActivityLogService = Depends(_get_service),
):
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
