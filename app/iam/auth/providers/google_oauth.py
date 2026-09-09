"""Google OAuth authentication provider.

Routes are thin parsers; all business logic lives in ``GoogleOAuthService``.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request

from app.core.database import SessionDep
from app.core.logging import get_logger
from app.core.utils import utc_now
from app.iam.auth.activity import ActivityAction, log_activity
from app.iam.auth.exceptions import InvalidTokenError
from app.iam.auth.providers import Provider
from app.iam.auth.schemas import GoogleAuthRequest, TokenResponse
from app.iam.auth.services import (
    AccountProvisioningService,
    TokenService,
)
from app.iam.config import auth_config
from app.iam.dependencies import (
    AccountProvisioningServiceDep,
    TokenServiceDep,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


PROVIDER_NAME = "google_oauth"


def _verify_google_id_token(id_token_str: str) -> dict:
    """Verify a Google ID token and return its claims.

    Wraps the google-auth library; raises :class:`InvalidTokenError` on any
    verification failure or when the library isn't installed.
    """
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError:
        raise InvalidTokenError("Google auth library not installed")

    try:
        return id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), auth_config.GOOGLE_CLIENT_ID
        )
    except ValueError:
        logger.warning("Invalid Google ID token")
        raise InvalidTokenError("Invalid Google Auth token")


class GoogleOAuthService:
    """Authenticate a Google ID token and issue session tokens."""

    def __init__(
        self,
        token_service: TokenService,
        provisioning: AccountProvisioningService,
    ):
        self.token_service = token_service
        self.provisioning = provisioning

    async def authenticate(
        self,
        session: AsyncSession,
        id_token_str: str,
        *,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        claims = _verify_google_id_token(id_token_str)

        external_id = claims.get("sub")
        email = claims.get("email")
        email_verified = bool(claims.get("email_verified", False))

        if not external_id or not email:
            raise InvalidTokenError("Google token missing required claims")
        if not email_verified:
            raise InvalidTokenError("Google email is not verified")

        user = await self.provisioning.find_or_create_by_oauth(
            session,
            provider=PROVIDER_NAME,
            external_id=external_id,
            email=email,
            full_name=claims.get("name"),
            avatar_url=claims.get("picture"),
        )

        user.last_login_at = utc_now()

        await log_activity(
            actor_id=user.id,
            action=ActivityAction.LOGIN,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=user.full_name,
            ip_address=ip_address,
            details={"email": user.email, "provider": PROVIDER_NAME},
        )

        return await self.token_service.issue_tokens(
            session, user, device_info=device_info, ip_address=ip_address
        )


# ── DI wiring ─────────────────────────────────────────────────────────────────

def get_google_oauth_service(
    token_service: TokenServiceDep,
    provisioning: AccountProvisioningServiceDep,
) -> GoogleOAuthService:
    return GoogleOAuthService(token_service=token_service, provisioning=provisioning)


GoogleOAuthServiceDep = Annotated[GoogleOAuthService, Depends(get_google_oauth_service)]


# ── Routes ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/google", tags=["Auth: Google OAuth"])


@router.post("")
async def google_auth(
    token_data: GoogleAuthRequest,
    request: Request,
    session: SessionDep,
    service: GoogleOAuthServiceDep,
) -> TokenResponse:
    """Authenticate with a Google ID token; creates an account on first use."""
    device_info = token_data.device_info or request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return await service.authenticate(
        session, token_data.id_token, device_info=device_info, ip_address=ip_address
    )


provider = Provider(
    name=PROVIDER_NAME,
    router=router,
    permissions=[
        ("auth", "google_link", "Can link/unlink Google account"),
    ],
    role_permissions={
        "member": ["auth:google_link"],
    },
)
