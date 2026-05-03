"""
Shared SQLAlchemy query helpers: sorting and windowed pagination.

``apply_sorting``    — whitelist-guarded dynamic ORDER BY with stable tiebreaker.
``paginated_select`` — single-query ``count() OVER ()`` pagination pattern.
"""

from typing import Any, List, Optional, Sequence, Tuple

from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement


def apply_sorting(
    query,
    model,
    sort_by: Optional[str],
    sort_order: str = "desc",
    allowed_fields: Optional[List[str]] = None,
    default_field: str = "created_at",
    default_order: str = "desc",
    tiebreaker_field: Optional[str] = "id",
):
    """Apply dynamic sorting to a SQLAlchemy query.

    Args:
        query: The SQLAlchemy ``select`` statement.
        model: The SQLAlchemy model class.
        sort_by: Column name to sort by (from the API query param).
        sort_order: ``"asc"`` or ``"desc"`` (from the API query param).
        allowed_fields: Whitelist of sortable column names.  If ``None``,
            any attribute that exists on the model is accepted.
        default_field: Fallback column when ``sort_by`` is ``None`` or invalid.
        default_order: Fallback direction when using the default field.
        tiebreaker_field: Secondary sort column appended for deterministic
            ``OFFSET``/``LIMIT`` pagination (default ``"id"``).
            Pass ``None`` to opt out.

    Returns:
        The query with ``order_by`` applied.
    """
    effective_field = default_field
    effective_order = default_order

    if sort_by:
        if allowed_fields and sort_by not in allowed_fields:
            pass  # invalid — keep defaults
        elif hasattr(model, sort_by):
            effective_field = sort_by
            effective_order = sort_order

    column = getattr(model, effective_field, None)
    if column is None:
        column = model.id  # last-resort fallback

    primary = column.asc() if effective_order == "asc" else column.desc()

    if (
        tiebreaker_field
        and tiebreaker_field != effective_field
        and hasattr(model, tiebreaker_field)
    ):
        tiebreaker_col = getattr(model, tiebreaker_field)
        return query.order_by(primary, tiebreaker_col.desc())
    return query.order_by(primary)


async def paginated_select(
    session: AsyncSession,
    base_query: Select,
    *,
    skip: int,
    limit: int,
    order_clauses: Sequence[ColumnElement],
    extra_columns: Optional[Sequence[ColumnElement]] = None,
) -> Tuple[List[Any], int]:
    """Run a single windowed SELECT and return ``(items, total)``.

    Implements the ``count() OVER ()`` window-function pagination pattern:
    one round trip returns both the page slice and the un-paginated total.
    Substantially faster than the conventional two-query
    ``SELECT COUNT(*) FROM (subquery)`` + ``SELECT … LIMIT`` approach because
    the filter set is evaluated only once.

    Args:
        session: Active ``AsyncSession``.
        base_query: A ``select(Model)`` (or ``select(Model, col1, ...)``) with
            all ``WHERE`` / ``JOIN`` / ``GROUP BY`` clauses already applied.
            Do **not** pre-apply ``order_by`` / ``offset`` / ``limit`` — this
            helper owns them.
        skip: Number of rows to skip (``OFFSET``).
        limit: Maximum rows to return (``LIMIT``).
        order_clauses: Order-by expressions.  Should end with a stable
            tiebreaker (e.g. ``model.id.desc()``) for deterministic paging.
        extra_columns: Additional columns already present in ``base_query``.
            When provided each item is a tuple where ``item[0]`` is the model
            instance and ``item[1:]`` are the extra column values.
            When omitted, items are model instances directly.

    Returns:
        ``(items, total)`` — ``items`` is a list of model instances (or tuples
        when ``extra_columns`` is set); ``total`` is the un-paginated row count.
    """
    total_count = func.count().over().label("_total")
    stmt = (
        base_query.add_columns(total_count)
        .order_by(*order_clauses)
        .offset(skip)
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    if not rows:
        return [], 0

    if extra_columns:
        # Row layout: [model, *extra_columns, _total]
        n_extra = len(extra_columns)
        items: List[Any] = [tuple(row[: 1 + n_extra]) for row in rows]
    else:
        # Row layout: [model, _total]
        items = [row[0] for row in rows]

    total = rows[0][-1]
    return items, int(total or 0)


__all__ = [
    "apply_sorting",
    "paginated_select",
]
