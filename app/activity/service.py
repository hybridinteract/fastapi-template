"""Activity log service — business logic layer."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from .crud import ActivityLogCRUD
from .schemas import ActivityLogListResponse, ActivityLogResponse

logger = get_logger(__name__)


class ActivityLogService:
    """Service layer for activity log operations."""

    def __init__(self, crud: ActivityLogCRUD):
        self._crud = crud

    async def list_logs(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        actor_id: Optional[UUID] = None,
        actor_name: Optional[str] = None,
        action: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ActivityLogListResponse:
        """Fetch paginated, filtered activity logs."""
        items, total = await self._crud.get_logs_with_count(
            session,
            skip=skip,
            limit=limit,
            actor_id=actor_id,
            actor_name=actor_name,
            action=action,
            date_from=date_from,
            date_to=date_to,
        )
        return ActivityLogListResponse(
            items=[ActivityLogResponse.model_validate(i) for i in items],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def bulk_delete(
        self,
        session: AsyncSession,
        ids: list[UUID],
    ) -> int:
        """Hard delete activity logs by IDs."""
        count = await self._crud.bulk_delete(session, ids)
        await session.commit()
        logger.info(f"Hard-deleted {count} activity log(s)")
        return count
