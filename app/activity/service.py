"""Activity log service — business logic layer."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from .crud import ActivityLogCRUD
from .schemas import (
    ActivityListParams,
    ActivityLogListResponse,
    ActivityLogResponse,
)

logger = get_logger(__name__)


class ActivityLogService:
    """Service layer for activity log operations."""

    def __init__(self, crud: ActivityLogCRUD):
        self._crud = crud

    async def list_logs(
        self,
        session: AsyncSession,
        params: ActivityListParams,
    ) -> ActivityLogListResponse:
        """Fetch paginated, filtered activity logs.

        Pass-through by design (conventions §10): business-rule narrowing would
        happen here via ``params.model_copy(update={...})``, never by mutating
        ``params``, which is frozen.
        """
        items, total = await self._crud.get_list_filtered(session, params)
        return ActivityLogListResponse(
            items=[ActivityLogResponse.model_validate(i) for i in items],
            total=total,
            skip=params.skip,
            limit=params.limit,
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
