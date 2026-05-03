"""
CRUDBase — generic async base class for model-level database operations.

Rules (PROJECT_CONVENTIONS §3.1):
  - NO session.commit() calls here — the Service layer owns transactions.
  - Use session.flush() to persist and obtain database-generated IDs.
  - Use session.refresh() after flush to keep ORM objects fully loaded.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base CRUD class with common database operations."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, session: AsyncSession, id: Any) -> Optional[ModelType]:
        """Fetch a single record by primary key. Returns ``None`` if not found."""
        result = await session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self, session: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Fetch a page of records ordered by ``id``. No filter, no total count.

        For filtered, sorted, and counted list endpoints use ``paginated_select()``
        from ``app.core.crud`` — see ``app/core/crud/README.md``.
        """
        result = await session.execute(
            select(self.model).offset(skip).limit(
                limit).order_by(self.model.id)
        )
        return list(result.scalars().all())

    async def create(
        self, session: AsyncSession, *, obj_in: CreateSchemaType
    ) -> ModelType:
        """Insert a new record and flush to obtain the DB-generated ``id``.

        Calls ``flush()`` + ``refresh()`` so the returned object is fully
        hydrated. Does **not** commit — the service layer owns that.
        """
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        session: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> ModelType:
        """Apply a partial update to an existing record. Does **not** commit.

        Accepts a Pydantic schema (``exclude_unset=True`` applied automatically)
        or a plain ``dict``. Fields absent from ``obj_in`` are left unchanged.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if update_data:
            for field, value in update_data.items():
                setattr(db_obj, field, value)
            await session.flush()
            await session.refresh(db_obj)

        return db_obj

    async def remove(self, session: AsyncSession, *, id: int) -> bool:
        """Hard-delete a record by primary key. Does **not** commit.

        Returns ``True`` if a row was deleted, ``False`` if the id was not found.
        For soft-delete semantics override this method or set ``is_deleted`` directly.
        """
        result = await session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await session.flush()
        return result.rowcount > 0

    async def count(self, session: AsyncSession) -> int:
        """Return the total un-filtered row count for the model table."""
        result = await session.execute(select(func.count(self.model.id)))
        return result.scalar() or 0

    async def exists(self, session: AsyncSession, id: Any) -> bool:
        """Return ``True`` if a record with the given primary key exists."""
        result = await session.execute(
            select(self.model.id).where(self.model.id == id)
        )
        return result.scalar_one_or_none() is not None


__all__ = [
    "CRUDBase",
    "ModelType",
    "CreateSchemaType",
    "UpdateSchemaType",
]
