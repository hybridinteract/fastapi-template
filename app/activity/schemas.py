"""Activity log schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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

    ids: list[UUID] = Field(..., min_length=1, max_length=200)
