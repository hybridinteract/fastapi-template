"""Token primitives — password hashing, JWT encode/decode, refresh token bytes.

Lifecycle operations (issue / refresh / revoke) live on ``TokenService`` in
``app.user.auth.services``. This module is dependency-free of CRUD/session
so it can be imported anywhere.

Hashing uses pwdlib (Argon2 for new hashes, bcrypt retained for verification
of hashes written by the previous passlib implementation). JWT uses PyJWT.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.settings import settings
from app.user.config import auth_config

# Order matters: the first hasher hashes new passwords, every hasher is tried
# when verifying. Argon2 is the algorithm FastAPI recommends; BcryptHasher is
# kept so credentials created before the pwdlib migration keep working.
password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False


def verify_and_update_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, Optional[str]]:
    """Verify a password and return an upgraded hash when one is warranted.

    The second element is a fresh Argon2 hash when ``hashed_password`` used an
    older scheme (e.g. a legacy bcrypt hash), otherwise ``None``. Callers that
    persist it migrate credentials transparently on next sign-in.
    """
    try:
        return password_hash.verify_and_update(plain_password, hashed_password)
    except UnknownHashError:
        return False, None


def generate_refresh_token_raw() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=auth_config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate token",
            headers={"WWW-Authenticate": "Bearer"},
        )
