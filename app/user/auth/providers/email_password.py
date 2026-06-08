"""Email + password authentication provider.

Routes are thin parsers; all business logic lives in ``EmailPasswordService``.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionDep
from app.core.logging import get_logger
from app.core.utils import utc_now
from app.user.auth.activity import ActivityAction, log_activity
from app.user.auth.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    PasswordLoginUnavailableError,
)
from app.user.auth.providers import Provider
from app.user.auth.schemas import (
    ChangePasswordRequest,
    TokenResponse,
    UserLogin,
)
from app.user.auth.services import TokenService, assert_user_active
from app.user.auth.tokens import get_password_hash, verify_password
from app.user.dependencies import CurrentUserDep, TokenServiceDep
from app.user.exceptions import UserAlreadyExistsError
from app.user.user.models import User
from app.user.user.crud import UserCRUD, user_crud
from app.user.user.query_service import UserQueryService
from app.user.user.schemas import UserCreate, UserResponse

logger = get_logger(__name__)


class EmailPasswordService:
    """Register / login / change-password for the email+password provider.

    Owns the transaction for register and change-password. Login defers commit
    to ``TokenService.issue_tokens`` which commits after token persistence.
    """

    def __init__(self, user_crud: UserCRUD, token_service: TokenService):
        self.user_crud = user_crud
        self.token_service = token_service

    async def register(
        self, session: AsyncSession, data: UserCreate
    ) -> UserResponse:
        if await self.user_crud.get_by_email(session, data.email):
            raise UserAlreadyExistsError(data.email)

        hashed = get_password_hash(data.password)
        user = await self.user_crud.create_with_password(
            session, obj_in=data, hashed_password=hashed
        )
        await session.commit()
        await session.refresh(user)

        await log_activity(
            actor_id=user.id,
            action=ActivityAction.REGISTER,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=user.full_name,
            details={"email": user.email},
        )
        return UserResponse.model_validate(user)

    async def login(
        self,
        session: AsyncSession,
        credentials: UserLogin,
        *,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        user = await self.user_crud.get_by_email(session, credentials.email)
        if not user:
            raise InvalidCredentialsError()
        if not user.hashed_password:
            raise PasswordLoginUnavailableError()
        if not verify_password(credentials.password, user.hashed_password):
            raise InvalidCredentialsError()
        assert_user_active(user)

        user.last_login_at = utc_now()

        await log_activity(
            actor_id=user.id,
            action=ActivityAction.LOGIN,
            resource_type="user",
            resource_id=str(user.id),
            actor_name=user.full_name,
            ip_address=ip_address,
            details={"email": user.email},
        )

        return await self.token_service.issue_tokens(
            session, user, device_info=device_info, ip_address=ip_address
        )

    async def change_password(
        self,
        session: AsyncSession,
        current_user: User,
        data: ChangePasswordRequest,
    ) -> None:
        if not current_user.hashed_password:
            raise InvalidCredentialsError("No password set for this account.")
        if not verify_password(data.current_password, current_user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")

        current_user.hashed_password = get_password_hash(data.new_password)
        current_user.updated_at = utc_now()
        await session.commit()
        await UserQueryService.invalidate_user(current_user.id)

        await log_activity(
            actor_id=current_user.id,
            action=ActivityAction.PASSWORD_CHANGE,
            resource_type="user",
            resource_id=str(current_user.id),
            actor_name=current_user.full_name,
            details={"email": current_user.email},
        )


# ── DI wiring ─────────────────────────────────────────────────────────────────

def get_email_password_service(
    token_service: TokenServiceDep,
) -> EmailPasswordService:
    return EmailPasswordService(user_crud=user_crud, token_service=token_service)


EmailPasswordServiceDep = Annotated[
    EmailPasswordService, Depends(get_email_password_service)
]


# ── Routes ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/password", tags=["Auth: Email/Password"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: SessionDep,
    service: EmailPasswordServiceDep,
) -> UserResponse:
    """Register a new user with email and password."""
    return await service.register(session, user_data)


@router.post("/login")
async def login(
    credentials: UserLogin,
    request: Request,
    session: SessionDep,
    service: EmailPasswordServiceDep,
) -> TokenResponse:
    """Authenticate with email and password; returns access + refresh tokens."""
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return await service.login(
        session, credentials, device_info=device_info, ip_address=ip_address
    )


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    service: EmailPasswordServiceDep,
) -> dict:
    """Change the authenticated user's password."""
    await service.change_password(session, current_user, data)
    return {"status": "success"}


provider = Provider(
    name="email_password",
    router=router,
    permissions=[
        ("auth", "password_change", "Can change their own password"),
    ],
    role_permissions={
        "member": ["auth:password_change"],
    },
)
