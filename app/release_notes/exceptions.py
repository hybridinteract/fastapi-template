"""Release-notes domain exceptions.

Every module owns an ``exceptions.py`` of named exceptions subclassing ``HTTPException``.
Services and routes never build a raw ``HTTPException(...)`` inline — see ``CLAUDE.md`` §6.
"""

from fastapi import HTTPException, status


class ReleaseNoteNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Release note not found",
        )


class ReleaseNoteVersionExistsError(HTTPException):
    def __init__(self, version: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Release note with version '{version}' already exists",
        )


__all__ = [
    "ReleaseNoteNotFoundError",
    "ReleaseNoteVersionExistsError",
]
