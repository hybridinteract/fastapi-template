"""Auth services — token lifecycle and shared account provisioning.

Per conventions §4: Services own commit/rollback; CRUD never commits.
Services receive CRUD via constructor (wired in ``app.user.dependencies``).
"""

from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.utils import utc_now
from app.user.auth.activity import ActivityAction, log_activity
from app.user.auth.crud import OAuthAccountCRUD, RefreshTokenCRUD
from app.user.auth.exceptions import InactiveUserError, InvalidTokenError
from app.user.auth.schemas import TokenResponse
from app.user.auth.tokens import (
    create_access_token,
    generate_refresh_token_raw,
    hash_token,
)
from app.user.config import auth_config
from app.user.enums import UserStatus
from app.user.user.models import User
from app.user.user.crud import UserCRUD

logger = get_logger(__name__)


def assert_user_active(user: User) -> None:
    """Raise :class:`InactiveUserError` if the user cannot sign in.

    Used by every auth provider; centralises the active/suspended check so
    new providers cannot accidentally skip it.
    """
    if not user.is_active or user.is_deleted:
        raise InactiveUserError()
    if user.status in (UserStatus.SUSPENDED, UserStatus.PENDING_VERIFICATION):
        raise InactiveUserError()


class TokenService:
    """Issues and manages access + refresh tokens. Owns commit."""

    def __init__(self, user_crud: UserCRUD, refresh_token_crud: RefreshTokenCRUD):
        self.user_crud = user_crud
        self.refresh_token_crud = refresh_token_crud

    async def issue_tokens(
        self,
        session: AsyncSession,
        user: User,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """Issue a new access + refresh token pair and commit."""
        access_token = create_access_token(str(user.id))
        refresh_raw = generate_refresh_token_raw()
        refresh_hash = hash_token(refresh_raw)

        expires_at = utc_now() + timedelta(
            days=auth_config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.refresh_token_crud.create_token(
            session,
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        await session.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_raw,
            expires_in=auth_config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
        )

    async def refresh_token(
        self, session: AsyncSession, refresh_token: str
    ) -> TokenResponse:
        """Rotate a refresh token (revoke old + issue new) and commit."""
        token_hash = hash_token(refresh_token)
        db_token = await self.refresh_token_crud.get_by_token_hash(
            session, token_hash, for_update=True
        )
        if not db_token:
            logger.warning("Refresh token not found")
            raise InvalidTokenError("Invalid refresh token")
        if db_token.is_revoked:
            logger.warning(f"Revoked token used for user_id={db_token.user_id}")
            raise InvalidTokenError("Refresh token has been revoked")
        if db_token.expires_at < utc_now():
            logger.warning(f"Expired token used for user_id={db_token.user_id}")
            raise InvalidTokenError("Refresh token has expired")

        user = await self.user_crud.get(session, db_token.user_id)
        if not user or not user.is_active or user.is_deleted:
            raise InvalidTokenError("User not found or inactive")
        if user.status in (UserStatus.SUSPENDED, UserStatus.PENDING_VERIFICATION):
            raise InvalidTokenError("User account is not active")

        new_access = create_access_token(str(user.id))
        new_refresh_raw = generate_refresh_token_raw()
        new_refresh_hash = hash_token(new_refresh_raw)

        db_token.is_revoked = True
        expires_at = utc_now() + timedelta(
            days=auth_config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.refresh_token_crud.create_token(
            session,
            user_id=user.id,
            token_hash=new_refresh_hash,
            expires_at=expires_at,
            device_info=db_token.device_info,
            ip_address=db_token.ip_address,
        )
        await session.commit()
        logger.info(f"Token refreshed for user_id={user.id}")

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh_raw,
            expires_in=auth_config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
        )

    async def logout(self, session: AsyncSession, refresh_token: str) -> bool:
        """Revoke a single refresh token (logout current session)."""
        token_hash = hash_token(refresh_token)
        db_token = await self.refresh_token_crud.get_by_token_hash(session, token_hash)
        if not db_token:
            return False

        db_token.is_revoked = True
        await session.flush()
        await session.commit()

        await log_activity(
            actor_id=db_token.user_id,
            action=ActivityAction.LOGOUT,
            resource_type="user",
            resource_id=str(db_token.user_id),
            details={"summary": "User logged out"},
        )
        return True

    async def logout_all(self, session: AsyncSession, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user (logout from all devices)."""
        count = await self.refresh_token_crud.revoke_all_user_tokens(session, user_id)
        await session.commit()

        if count:
            await log_activity(
                actor_id=user_id,
                action=ActivityAction.LOGOUT,
                resource_type="user",
                resource_id=str(user_id),
                details={
                    "summary": "Logged out from all devices",
                    "revoked_tokens": count,
                },
            )
        return count


class AccountProvisioningService:
    """Find-or-create a user from an external identity (OAuth, phone, etc.).

    Caller owns the transaction. This service only flushes; the route or
    higher-level service commits after token issuance.
    """

    def __init__(self, user_crud: UserCRUD, oauth_account_crud: OAuthAccountCRUD):
        self.user_crud = user_crud
        self.oauth_account_crud = oauth_account_crud

    async def find_or_create_by_oauth(
        self,
        session: AsyncSession,
        *,
        provider: str,
        external_id: str,
        email: Optional[str],
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> User:
        """Resolve a user by OAuth identity, linking or creating as needed."""
        oauth_acc = await self.oauth_account_crud.get_by_provider(
            session, provider, external_id
        )
        if oauth_acc:
            user = await self.user_crud.get(session, oauth_acc.user_id)
            if not user:
                raise InvalidTokenError("Linked user no longer exists")
            assert_user_active(user)
            return user

        if email:
            existing = await self.user_crud.get_by_email(session, email)
            if existing:
                assert_user_active(existing)
                await self.oauth_account_crud.link(
                    session,
                    user_id=existing.id,
                    provider=provider,
                    provider_user_id=external_id,
                    email=email,
                )
                return existing

        user = User(
            email=email,
            hashed_password=None,
            full_name=full_name,
            avatar_url=avatar_url,
            email_verified=bool(email),
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        await self.oauth_account_crud.link(
            session,
            user_id=user.id,
            provider=provider,
            provider_user_id=external_id,
            email=email,
        )
        return user

    async def find_or_create_by_phone(
        self, session: AsyncSession, *, phone: str
    ) -> User:
        """Resolve a user by phone, creating an active account if absent."""
        user = await self.user_crud.get_by_phone(session, phone)
        if user:
            assert_user_active(user)
            return user

        user = User(
            phone=phone,
            hashed_password=None,
            email_verified=False,
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user
