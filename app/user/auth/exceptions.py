"""Auth-domain exceptions (credentials, tokens, provider-specific failures)."""

from fastapi import HTTPException, status


class InvalidCredentialsError(HTTPException):
    """Raised when login credentials are invalid."""

    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InactiveUserError(HTTPException):
    """Raised when user account is inactive, suspended, or pending verification."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )


class InvalidTokenError(HTTPException):
    """Raised when a JWT / refresh token is invalid, expired, or revoked."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PasswordLoginUnavailableError(HTTPException):
    """Raised when an account exists but has no password (e.g. OAuth-only)."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This account was created with a third-party provider (e.g. Google). "
                "Sign in with that provider, then set a password from your profile."
            ),
        )


class InvalidOTPError(HTTPException):
    def __init__(self, detail: str = "Invalid or expired OTP"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class TooManyOTPAttemptsError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts",
        )
