"""Current user dependency — extracts and validates the bearer token.

A dependency (not a route), so it may call CRUD directly per conventions §4.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.database import SessionDep
from app.user.auth.tokens import decode_token
from app.user.config import auth_config
from app.user.enums import UserStatus
from app.user.user.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/password/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    """Decode the bearer token and return the active User."""
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Deferred import: user.crud transitively pulls permission_management,
    # whose __init__ imports this module. Importing here breaks the cycle.
    from app.user.user.crud import user_crud

    user = await user_crud.get_user_with_roles(session, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    if user.status in (UserStatus.SUSPENDED, UserStatus.PENDING_VERIFICATION):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_active_superuser(current_user: CurrentUserDep) -> User:
    if current_user.is_superuser:
        return current_user
    if any(r.name == auth_config.SUPER_ADMIN_ROLE for r in current_user.roles):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions",
    )


SuperUserDep = Annotated[User, Depends(get_current_active_superuser)]
