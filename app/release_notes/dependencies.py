from typing import Annotated

from fastapi import Depends

from .crud import release_note_crud
from .service import ReleaseNoteService


def get_release_note_service() -> ReleaseNoteService:
    return ReleaseNoteService(crud=release_note_crud)


ReleaseNoteServiceDep = Annotated[ReleaseNoteService, Depends(get_release_note_service)]
