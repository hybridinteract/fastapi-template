"""Auth-domain CRUD — refresh tokens, OAuth accounts, phone OTPs. Never commits."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import CRUDBase
from app.core.utils import utc_now
from app.iam.auth.models import OAuthAccount, PhoneOTP, RefreshToken


# ── RefreshToken ──────────────────────────────────────────────────────────────

class RefreshTokenCRUD(CRUDBase[RefreshToken, BaseModel, BaseModel]):

    def __init__(self):
        super().__init__(RefreshToken)

    async def create_token(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        session.add(token)
        await session.flush()
        await session.refresh(token)
        return token

    async def get_by_token_hash(
        self, session: AsyncSession, token_hash: str, for_update: bool = False
    ) -> Optional[RefreshToken]:
        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:
            query = query.with_for_update()
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def revoke_all_user_tokens(self, session: AsyncSession, user_id: UUID) -> int:
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.is_revoked == False
            )
        )
        tokens = result.scalars().all()
        count = 0
        for token in tokens:
            token.is_revoked = True
            count += 1
        await session.flush()
        return count

    async def cleanup_expired(self, session: AsyncSession) -> int:
        result = await session.execute(
            sa_delete(RefreshToken).where(RefreshToken.expires_at < utc_now())
        )
        await session.flush()
        return result.rowcount or 0

    async def get_user_tokens(
        self, session: AsyncSession, user_id: UUID, include_revoked: bool = False
    ) -> List[RefreshToken]:
        query = select(RefreshToken).where(RefreshToken.user_id == user_id)
        if not include_revoked:
            query = query.where(RefreshToken.is_revoked == False)
        result = await session.execute(query.order_by(RefreshToken.created_at.desc()))
        return list(result.scalars().all())


# ── OAuthAccount ──────────────────────────────────────────────────────────────

class OAuthAccountCRUD(CRUDBase[OAuthAccount, BaseModel, BaseModel]):

    def __init__(self):
        super().__init__(OAuthAccount)

    async def get_by_provider(
        self, session: AsyncSession, provider: str, provider_user_id: str
    ) -> Optional[OAuthAccount]:
        result = await session.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, session: AsyncSession, user_id: UUID) -> List[OAuthAccount]:
        result = await session.execute(
            select(OAuthAccount)
            .where(OAuthAccount.user_id == user_id)
            .order_by(OAuthAccount.linked_at.desc())
        )
        return list(result.scalars().all())

    async def link(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        provider: str,
        provider_user_id: str,
        email: Optional[str] = None,
    ) -> OAuthAccount:
        account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )
        session.add(account)
        await session.flush()
        await session.refresh(account)
        return account

    async def unlink(
        self, session: AsyncSession, *, user_id: UUID, provider: str
    ) -> bool:
        result = await session.execute(
            sa_delete(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
        )
        await session.flush()
        return (result.rowcount or 0) > 0


# ── PhoneOTP ──────────────────────────────────────────────────────────────────

class PhoneOTPCRUD(CRUDBase[PhoneOTP, BaseModel, BaseModel]):

    def __init__(self):
        super().__init__(PhoneOTP)

    async def create_otp(
        self,
        session: AsyncSession,
        *,
        phone: str,
        otp_hash: str,
        expires_at: datetime,
        user_id: Optional[UUID] = None,
    ) -> PhoneOTP:
        otp = PhoneOTP(
            phone=phone,
            otp_hash=otp_hash,
            expires_at=expires_at,
            user_id=user_id,
        )
        session.add(otp)
        await session.flush()
        await session.refresh(otp)
        return otp

    async def get_valid_otp(
        self, session: AsyncSession, phone: str, for_update: bool = False
    ) -> Optional[PhoneOTP]:
        query = (
            select(PhoneOTP)
            .where(
                PhoneOTP.phone == phone,
                PhoneOTP.consumed_at.is_(None),
                PhoneOTP.expires_at > utc_now(),
            )
            .order_by(PhoneOTP.created_at.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def consume_otp(self, session: AsyncSession, otp: PhoneOTP) -> PhoneOTP:
        otp.consumed_at = utc_now()
        await session.flush()
        await session.refresh(otp)
        return otp

    async def increment_attempts(self, session: AsyncSession, otp: PhoneOTP) -> PhoneOTP:
        otp.attempts = (otp.attempts or 0) + 1
        await session.flush()
        return otp

    async def invalidate_all_for_phone(self, session: AsyncSession, phone: str) -> int:
        result = await session.execute(
            sa_delete(PhoneOTP).where(PhoneOTP.phone == phone)
        )
        await session.flush()
        return result.rowcount or 0

    async def cleanup_expired(self, session: AsyncSession) -> int:
        result = await session.execute(
            sa_delete(PhoneOTP).where(PhoneOTP.expires_at < utc_now())
        )
        await session.flush()
        return result.rowcount or 0


# ── Module-level singletons ───────────────────────────────────────────────────

refresh_token_crud = RefreshTokenCRUD()
oauth_account_crud = OAuthAccountCRUD()
phone_otp_crud = PhoneOTPCRUD()
