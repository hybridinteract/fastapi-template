"""Activity log CRUD operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, delete, over
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ActivityLog


class ActivityLogCRUD:
    """CRUD operations for ActivityLog model."""

    async def get_logs_with_count(
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
    ) -> tuple[list[ActivityLog], int]:
        """
        Get activity logs with filters and total count in a single query.

        Uses a window function (COUNT(*) OVER()) to piggyback the total
        count onto the paginated result set — one DB round-trip instead of two.
        """
        filters = self._build_filters(
            actor_id=actor_id,
            actor_name=actor_name,
            action=action,
            date_from=date_from,
            date_to=date_to,
        )

        total_count = func.count().over().label("_total")
        query = (
            select(ActivityLog, total_count)
            .where(*filters)
            .order_by(ActivityLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return [], 0

        items = [row[0] for row in rows]
        total = rows[0][1]  # same on every row

        return items, total

    async def bulk_delete(
        self,
        session: AsyncSession,
        ids: list[UUID],
    ) -> int:
        """Hard delete activity logs by IDs. Does NOT commit."""
        if not ids:
            return 0
        result = await session.execute(
            delete(ActivityLog).where(ActivityLog.id.in_(ids))
        )
        await session.flush()
        return result.rowcount

    @staticmethod
    def _build_filters(
        *,
        actor_id: Optional[UUID] = None,
        actor_name: Optional[str] = None,
        action: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list:
        """Build WHERE clauses from filter params."""
        filters = []
        if actor_id is not None:
            filters.append(ActivityLog.actor_id == actor_id)
        if actor_name is not None:
            filters.append(ActivityLog.actor_name.ilike(f"%{actor_name}%"))
        if action is not None:
            filters.append(ActivityLog.action == action.upper())
        if date_from is not None:
            filters.append(ActivityLog.created_at >= date_from)
        if date_to is not None:
            filters.append(ActivityLog.created_at <= date_to)
        return filters


activity_log_crud = ActivityLogCRUD()
