"""
Authentication service.
"""

from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.settings import settings
from app.core.utils import utc_now
from ..models import User, UserStatus
from ..schemas import UserCreate, UserLogin, TokenResponse
from ..crud import user_crud
from ..crud.refresh_token_crud import refresh_token_crud
from ..exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    InactiveUserError,
    InvalidTokenError,
)
from .utils import (
    get_password_hash,
    verify_password,
    create_access_token,
    generate_refresh_token_raw,
    hash_token,
)
from app.activity import activity, ActivityAction

logger = get_logger(__name__)


class AuthService:
    """Authentication service for user login and registration."""

    @staticmethod
    async def register(
        session: AsyncSession,
        user_data: UserCreate
    ) -> User:
        """Register a new user."""
        # Check if user exists
        existing = await user_crud.get_by_email(session, user_data.email)
        if existing:
            raise UserAlreadyExistsError(user_data.email)

        # Hash password and create user
        hashed_password = get_password_hash(user_data.password)
        user = await user_crud.create_with_password(
            session,
            obj_in=user_data,
            hashed_password=hashed_password
        )

        await session.commit()
        await session.refresh(user)

        logger.info(f"User registered: {user.email}")
        return user

    @staticmethod
    async def login(
        session: AsyncSession,
        credentials: UserLogin,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """Authenticate user and return tokens.

        Args:
            session: Database session
            credentials: Login credentials
            device_info: User-Agent string for device tracking
            ip_address: Client IP address
        """
        # Get user
        user = await user_crud.get_by_email(session, credentials.email)
        if not user:
            raise InvalidCredentialsError()

        # Verify password
        if not verify_password(credentials.password, user.hashed_password):
            raise InvalidCredentialsError()

        # Check if active and not deleted/suspended
        if not user.is_active or user.is_deleted:
            raise InactiveUserError()

        if user.status in (UserStatus.SUSPENDED, UserStatus.PENDING_VERIFICATION):
            raise InactiveUserError()

        # Update last login timestamp
        user.last_login_at = utc_now()

        # Generate tokens
        access_token = create_access_token(str(user.id))
        refresh_token_raw = generate_refresh_token_raw()
        refresh_token_hash = hash_token(refresh_token_raw)

        # Store refresh token in database
        expires_at = utc_now() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        await refresh_token_crud.create_token(
            session,
            user_id=user.id,
            token_hash=refresh_token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )

        await session.commit()

        logger.info(f"User logged in: {user.email}")
        activity.log(
            actor_id=user.id,
            action=ActivityAction.LOGIN,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=user.full_name,
            ip_address=ip_address,
            details={"summary": f"{user.email} logged in"},
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_raw,  # Send raw token to client
        )

    @staticmethod
    async def refresh_token(
        session: AsyncSession,
        refresh_token: str
    ) -> TokenResponse:
        """Refresh access token using a refresh token.

        Validates the token exists in DB, is not revoked, and is not expired.
        Uses SELECT FOR UPDATE to prevent race conditions on concurrent refreshes.
        """
        # Hash the incoming token to look it up in the database
        token_hash = hash_token(refresh_token)

        # Lookup token with row lock to prevent concurrent refresh race condition
        db_token = await refresh_token_crud.get_by_token_hash(
            session, token_hash, for_update=True
        )
        if not db_token:
            logger.warning("Refresh token not found")
            raise InvalidTokenError("Invalid refresh token")

        # Check if revoked
        if db_token.is_revoked:
            logger.warning(f"Revoked refresh token used for user_id={db_token.user_id}")
            raise InvalidTokenError("Refresh token has been revoked")

        # Check if expired
        if db_token.expires_at < utc_now():
            logger.warning(f"Expired refresh token used for user_id={db_token.user_id}")
            raise InvalidTokenError("Refresh token has expired")

        # Verify user exists and is active
        user = await user_crud.get(session, db_token.user_id)
        if not user or not user.is_active or user.is_deleted:
            raise InvalidTokenError("User not found or inactive")

        if user.status in (UserStatus.SUSPENDED, UserStatus.PENDING_VERIFICATION):
            raise InvalidTokenError("User account is not active")

        # Generate new tokens
        new_access_token = create_access_token(str(user.id))
        new_refresh_token_raw = generate_refresh_token_raw()
        new_refresh_token_hash = hash_token(new_refresh_token_raw)

        # Revoke old token
        db_token.is_revoked = True

        # Create new refresh token in database
        expires_at = utc_now() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        await refresh_token_crud.create_token(
            session,
            user_id=user.id,
            token_hash=new_refresh_token_hash,
            expires_at=expires_at,
            device_info=db_token.device_info,  # Preserve device info
            ip_address=db_token.ip_address,    # Preserve IP
        )

        await session.commit()

        logger.info(f"Token refreshed for user: {user.email}")

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token_raw,
        )

    @staticmethod
    async def logout(
        session: AsyncSession,
        refresh_token: str,
    ) -> bool:
        """Revoke a refresh token (logout).

        Returns True if token was revoked, False if not found.
        """
        token_hash = hash_token(refresh_token)
        db_token = await refresh_token_crud.get_by_token_hash(session, token_hash)
        if not db_token:
            return False

        db_token.is_revoked = True
        await session.flush()
        await session.commit()

        activity.log(
            actor_id=db_token.user_id,
            action=ActivityAction.LOGOUT,
            resource_type="user",
            resource_id=str(db_token.user_id),
            details={"summary": "User logged out"},
        )

        return True

    @staticmethod
    async def logout_all(
        session: AsyncSession,
        user_id,
    ) -> int:
        """Revoke all refresh tokens for a user (logout from all devices).

        Returns the number of tokens revoked.
        """
        count = await refresh_token_crud.revoke_all_user_tokens(session, user_id)
        await session.commit()

        if count:
            activity.log(
                actor_id=user_id,
                action=ActivityAction.LOGOUT,
                resource_type="user",
                resource_id=str(user_id),
                details={"summary": "User logged out from all devices", "revoked_tokens": count},
            )

        return count

    @staticmethod
    async def change_password(
        session: AsyncSession,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password.

        Validates current password before updating.
        """
        # Get user
        user = await user_crud.get(session, user_id)
        if not user:
            raise InvalidCredentialsError()

        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")

        # Hash and update new password
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = utc_now()

        await session.commit()
        await session.refresh(user)

        logger.info(f"Password changed for user: {user.email}")
        activity.log(
            actor_id=user.id,
            action=ActivityAction.PASSWORD_CHANGE,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=user.full_name,
            details={"summary": f"{user.email} changed their password"},
        )
        return True
