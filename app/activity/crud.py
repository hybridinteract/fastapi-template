"""Activity log CRUD operations."""

from datetime import date, datetime, time, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import paginated_select

from .models import ActivityLog
from .schemas import ActivityListParams


class ActivityLogCRUD:
    """CRUD operations for ActivityLog model."""

    async def get_list_filtered(
        self,
        session: AsyncSession,
        params: ActivityListParams,
    ) -> tuple[list[ActivityLog], int]:
        """
        Get activity logs with filters, sorting and total count in one query.

        Delegates to ``paginated_select``, which implements the shared
        ``COUNT(*) OVER ()`` window pattern — one DB round-trip returns both the
        page slice and the un-paginated total (conventions §10).
        """
        filters = self._build_filters(
            actor_id=params.actor_id,
            actor_name=params.actor_name,
            action=params.action,
            date_from=params.date_from,
            date_to=params.date_to,
        )

        # ``sort_by`` is a Literal validated at the route layer, so an unknown
        # column is already a 422 and this getattr cannot miss.
        sort_column = getattr(ActivityLog, params.sort_by or "created_at")
        direction = (
            sort_column.asc() if params.sort_order == "asc" else sort_column.desc()
        )

        return await paginated_select(
            session,
            select(ActivityLog).where(*filters),
            skip=params.skip,
            limit=params.limit,
            # id.desc() is the stable tiebreaker — without it, rows sharing a
            # sort value can repeat or vanish across pages.
            order_clauses=[direction, ActivityLog.id.desc()],
        )

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
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list:
        """Build WHERE clauses from filter params.

        ``date_from`` / ``date_to`` are calendar dates and both bounds are
        inclusive, so they are widened to cover the whole day in UTC. Without
        widening ``date_to``, a filter of ``date_to=2026-08-27`` would compare
        against midnight and silently exclude that entire day.
        """
        filters = []
        if actor_id is not None:
            filters.append(ActivityLog.actor_id == actor_id)
        if actor_name is not None:
            filters.append(ActivityLog.actor_name.ilike(f"%{actor_name}%"))
        if action is not None:
            filters.append(ActivityLog.action == str(action).upper())
        if date_from is not None:
            filters.append(
                ActivityLog.created_at
                >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
            )
        if date_to is not None:
            filters.append(
                ActivityLog.created_at
                <= datetime.combine(date_to, time.max, tzinfo=timezone.utc)
            )
        return filters


activity_log_crud = ActivityLogCRUD()
