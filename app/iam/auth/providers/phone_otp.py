"""Phone OTP authentication provider (enable via AUTH_PHONE_OTP_ENABLED=true).

Routes are thin parsers; all business logic lives in ``PhoneOTPService``.
"""

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionDep
from app.core.utils import utc_now
from app.iam.auth.activity import ActivityAction, log_activity
from app.iam.auth.crud import PhoneOTPCRUD, phone_otp_crud
from app.iam.auth.exceptions import InvalidOTPError, TooManyOTPAttemptsError
from app.iam.auth.providers import Provider
from app.iam.auth.schemas import OTPRequestSchema, OTPVerifySchema, TokenResponse
from app.iam.auth.services import AccountProvisioningService, TokenService
from app.iam.config import auth_config
from app.iam.dependencies import (
    AccountProvisioningServiceDep,
    TokenServiceDep,
)

logger = logging.getLogger(__name__)


PROVIDER_NAME = "phone_otp"


def _generate_otp(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _send_otp(phone: str, otp: str, sms_provider: str) -> None:
    if sms_provider == "noop":
        logger.info(f"[DEV OTP] phone={phone} otp={otp}")
        return
    raise NotImplementedError(f"SMS provider '{sms_provider}' not implemented")


class PhoneOTPService:
    """Request and verify phone OTPs; provision an account on first verify."""

    def __init__(
        self,
        phone_otp_crud: PhoneOTPCRUD,
        token_service: TokenService,
        provisioning: AccountProvisioningService,
    ):
        self.phone_otp_crud = phone_otp_crud
        self.token_service = token_service
        self.provisioning = provisioning

    async def request_otp(
        self, session: AsyncSession, phone: str
    ) -> dict:
        await self.phone_otp_crud.invalidate_all_for_phone(session, phone)

        otp_raw = _generate_otp(auth_config.OTP_LENGTH)
        otp_hash = _hash_otp(otp_raw)
        expires_at = utc_now() + timedelta(seconds=auth_config.OTP_TTL_SECONDS)

        await self.phone_otp_crud.create_otp(
            session, phone=phone, otp_hash=otp_hash, expires_at=expires_at
        )
        await session.commit()

        _send_otp(phone, otp_raw, auth_config.OTP_SMS_PROVIDER)
        return {"status": "sent", "expires_in": auth_config.OTP_TTL_SECONDS}

    async def verify_otp(
        self,
        session: AsyncSession,
        phone: str,
        otp: str,
        *,
        device_info: Optional[str] = None,
    ) -> TokenResponse:
        otp_record = await self.phone_otp_crud.get_valid_otp(
            session, phone, for_update=True
        )
        if not otp_record:
            raise InvalidOTPError()
        if (otp_record.attempts or 0) >= auth_config.OTP_MAX_ATTEMPTS:
            raise TooManyOTPAttemptsError()
        if otp_record.otp_hash != _hash_otp(otp):
            await self.phone_otp_crud.increment_attempts(session, otp_record)
            await session.commit()
            raise InvalidOTPError("Invalid OTP")

        await self.phone_otp_crud.consume_otp(session, otp_record)

        user = await self.provisioning.find_or_create_by_phone(session, phone=phone)
        user.last_login_at = utc_now()

        await log_activity(
            actor_id=user.id,
            action=ActivityAction.LOGIN,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=user.full_name,
            details={"phone": phone, "provider": PROVIDER_NAME},
        )

        return await self.token_service.issue_tokens(
            session, user, device_info=device_info
        )


# ── DI wiring ─────────────────────────────────────────────────────────────────

def get_phone_otp_service(
    token_service: TokenServiceDep,
    provisioning: AccountProvisioningServiceDep,
) -> PhoneOTPService:
    return PhoneOTPService(
        phone_otp_crud=phone_otp_crud,
        token_service=token_service,
        provisioning=provisioning,
    )


PhoneOTPServiceDep = Annotated[PhoneOTPService, Depends(get_phone_otp_service)]


# ── Routes ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/otp", tags=["Auth: Phone OTP"])


@router.post("/request")
async def request_otp(
    body: OTPRequestSchema,
    session: SessionDep,
    service: PhoneOTPServiceDep,
) -> dict:
    """Request a one-time password sent to the given phone number."""
    return await service.request_otp(session, body.phone)


@router.post("/verify")
async def verify_otp(
    body: OTPVerifySchema,
    session: SessionDep,
    service: PhoneOTPServiceDep,
) -> TokenResponse:
    """Verify the OTP and issue tokens. Creates an account if the phone is new."""
    return await service.verify_otp(
        session, body.phone, body.otp, device_info=body.device_info
    )


provider = Provider(
    name=PROVIDER_NAME,
    router=router,
    permissions=[
        ("auth", "phone_link", "Can link/unlink phone number for OTP login"),
    ],
    role_permissions={
        "member": ["auth:phone_link"],
    },
)
