"""
Base CRUD operations.

Provides a reusable, type-safe interface for CRUD operations
on SQLAlchemy models using Generic types.

IMPORTANT: CRUD methods do NOT commit. Service layer owns transactions.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base CRUD class with common database operations.
    
    Pattern:
    - NO session.commit() calls - Service layer owns transaction boundaries
    - USE session.flush() to persist and get database-generated IDs
    - USE session.refresh() to ensure objects are fully loaded
    """

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, session: AsyncSession, id: Any) -> Optional[ModelType]:
        """Get a single record by ID."""
        result = await session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, session: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records with pagination."""
        result = await session.execute(
            select(self.model).offset(skip).limit(limit).order_by(self.model.id)
        )
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record.
        Note: Does NOT commit. Call session.commit() from service layer.
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
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update an existing record.
        Note: Does NOT commit. Call session.commit() from service layer.
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
        """Delete a record by ID. Does NOT commit."""
        result = await session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await session.flush()
        return result.rowcount > 0

    async def count(self, session: AsyncSession) -> int:
        """Count total records."""
        result = await session.execute(select(func.count(self.model.id)))
        return result.scalar() or 0

    async def exists(self, session: AsyncSession, id: Any) -> bool:
        """Check if a record exists."""
        result = await session.execute(
            select(self.model.id).where(self.model.id == id)
        )
        return result.scalar_one_or_none() is not None
