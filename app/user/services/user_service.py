"""
User service - self-service operations.

Business logic for user's own profile management.
Routes call service methods; service calls CRUD for data access.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.user.models import User
from app.user.crud.user_crud import user_crud
from app.user.schemas.user_schemas import UserResponse, UserUpdateSelf
from app.user.exceptions import UserNotFoundError
from app.user.services.user_query_service import UserQueryService

logger = get_logger(__name__)


class UserService:
    """Business logic for user self-service operations."""

    @staticmethod
    async def get_my_profile(
        session: AsyncSession, 
        user_id: UUID
    ) -> UserResponse:
        """Get current user's profile."""
        user = await user_crud.get(session, user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(str(user_id))
        
        return UserResponse.model_validate(user)

    @staticmethod
    async def update_my_profile(
        session: AsyncSession,
        user_id: UUID,
        update_data: UserUpdateSelf
    ) -> UserResponse:
        """Update own profile (limited fields only)."""
        user = await user_crud.get(session, user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(str(user_id))

        # UserUpdateSelf schema should only allow safe fields like full_name, phone, avatar_url
        updates = update_data.model_dump(exclude_unset=True)
        
        # Check email uniqueness if email is being changed
        if "email" in updates and updates["email"] != user.email:
            existing = await user_crud.get_by_email(session, updates["email"])
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
        
        # Check phone uniqueness if phone is being changed
        if "phone" in updates and updates["phone"] != user.phone:
            existing_phone = await user_crud.get_by_phone(session, updates["phone"])
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone already in use"
                )

        user = await user_crud.update(session, db_obj=user, obj_in=updates)
        await session.commit()

        logger.info(f"User {user_id} updated their profile")
        await UserQueryService.invalidate_user_cache(user_id)
        return UserResponse.model_validate(user)


user_service = UserService()
