"""User-domain exceptions.

Auth-specific exceptions (credentials, tokens, OTP, provider failures) live in
``app.iam.auth.exceptions`` — import them from there directly.
"""

from fastapi import HTTPException, status


class UserNotFoundError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {identifier}",
        )


class UserAlreadyExistsError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already exists: {identifier}",
        )


__all__ = [
    "UserNotFoundError",
    "UserAlreadyExistsError",
]
