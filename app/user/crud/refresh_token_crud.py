"""
RefreshToken CRUD operations.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.core.crud import CRUDBase
from app.core.utils import utc_now
from app.user.models import RefreshToken


class RefreshTokenCRUD(CRUDBase[RefreshToken, BaseModel, BaseModel]):
    """CRUD operations for RefreshToken model."""

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
        """Create a new refresh token record.

        Does NOT commit — service layer owns the transaction.
        """
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
        self,
        session: AsyncSession,
        token_hash: str,
        for_update: bool = False,
    ) -> Optional[RefreshToken]:
        """Get refresh token by its hash."""
        query = select(self.model).where(self.model.token_hash == token_hash)
        if for_update:
            query = query.with_for_update()
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def revoke_token(
        self,
        session: AsyncSession,
        token_hash: str,
    ) -> bool:
        """Revoke a refresh token by setting is_revoked=True.

        Does NOT commit — service layer owns the transaction.
        Returns True if token was found and revoked, False otherwise.
        """
        token = await self.get_by_token_hash(session, token_hash)
        if not token:
            return False
        token.is_revoked = True
        await session.flush()
        return True

    async def revoke_all_user_tokens(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> int:
        """Revoke all refresh tokens for a user.

        Does NOT commit — service layer owns the transaction.
        Returns the number of tokens revoked.
        """
        query = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .where(self.model.is_revoked == False)
        )
        result = await session.execute(query)
        tokens = result.scalars().all()

        count = 0
        for token in tokens:
            token.is_revoked = True
            count += 1

        await session.flush()
        return count

    async def cleanup_expired(
        self,
        session: AsyncSession,
    ) -> int:
        """Delete expired refresh tokens.

        Does NOT commit — service layer owns the transaction.
        Returns the number of tokens deleted.
        """
        query = delete(self.model).where(self.model.expires_at < utc_now())
        result = await session.execute(query)
        await session.flush()
        return result.rowcount or 0

    async def get_user_tokens(
        self,
        session: AsyncSession,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> List[RefreshToken]:
        """Get all refresh tokens for a user.

        Args:
            user_id: User ID
            include_revoked: Whether to include revoked tokens (default: False)
        """
        query = select(self.model).where(self.model.user_id == user_id)
        if not include_revoked:
            query = query.where(self.model.is_revoked == False)
        query = query.order_by(self.model.created_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())


refresh_token_crud = RefreshTokenCRUD()
