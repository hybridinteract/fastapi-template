"""Activity log admin endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.database import SessionDep
from app.iam.permission import require_permission
from .dependencies import ActivityServiceDep
from .schemas import (
    ActivityListParams,
    ActivityLogListResponse,
    BulkDeleteRequest,
)

router = APIRouter(
    prefix="/activity-logs",
    tags=["Activity Logs"],
    dependencies=[Depends(require_permission("activity:read_all"))],
)


@router.get("", summary="List activity logs")
async def list_activity_logs(
    params: Annotated[ActivityListParams, Query()],
    session: SessionDep,
    service: ActivityServiceDep,
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
    return await service.list_logs(session, params)


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
