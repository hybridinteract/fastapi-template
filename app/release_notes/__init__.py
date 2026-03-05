"""
Release Notes Module.

Self-contained module for managing release notes / "What's New" announcements.
"""

from .models import ReleaseNote
from .crud import release_note_crud
from .service import ReleaseNoteService, release_note_service
from .routes import router as release_notes_router

__all__ = [
    "ReleaseNote",
    "release_note_crud",
    "ReleaseNoteService",
    "release_note_service",
    "release_notes_router",
]
