"""Activity log schemas."""

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import ListParams

from .enums import ActivityAction


class ActivityLogResponse(BaseModel):
    """Single activity log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID
    actor_name: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime


class ActivityLogListResponse(BaseModel):
    """Paginated activity log list."""

    items: list[ActivityLogResponse]
    total: int
    skip: int
    limit: int


class BulkDeleteRequest(BaseModel):
    """Request body for bulk hard delete."""

    ids: list[UUID] = Field(min_length=1, max_length=200)


class ActivityListParams(ListParams):
    """Query parameters for the activity log list endpoint.

    Reference implementation of the list-endpoint contract (conventions §10).
    Bound on the route with ``Annotated[ActivityListParams, Query()]`` — never
    ``Depends()``. Inherits ``skip`` / ``limit`` / ``sort_order`` from
    ``ListParams`` and is frozen, so business-rule overrides use
    ``params.model_copy(update={...})``.
    """

    # Preserve this endpoint's original page size; ListParams defaults to 100.
    limit: int = Field(
        50, ge=1, le=500, description="Maximum number of records to return."
    )
    sort_by: Optional[Literal["created_at", "action", "actor_name"]] = Field(
        None, description="Column to sort by. Defaults to newest first."
    )
    actor_id: Optional[UUID] = Field(
        None, description="Exact match — show only actions by this user."
    )
    actor_name: Optional[str] = Field(
        None, description="Partial, case-insensitive match on actor name."
    )
    action: Optional[ActivityAction] = Field(
        None, description="Filter by action type."
    )
    date_from: Optional[date] = Field(
        None, description="Start date, inclusive (YYYY-MM-DD)."
    )
    date_to: Optional[date] = Field(
        None, description="End date, inclusive (YYYY-MM-DD)."
    )
