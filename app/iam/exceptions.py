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


class PhoneAlreadyInUseError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already in use",
        )


class CannotDeleteSelfError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )


class UserNotDeletedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not deleted",
        )


class RoleNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )


class ProtectedRoleError(HTTPException):
    """The developer-admin role bypasses every check, so its grants are not editable."""

    def __init__(self, role_name: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify {role_name} permissions",
        )


__all__ = [
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "PhoneAlreadyInUseError",
    "CannotDeleteSelfError",
    "UserNotDeletedError",
    "RoleNotFoundError",
    "ProtectedRoleError",
]
