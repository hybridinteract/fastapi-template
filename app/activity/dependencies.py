from typing import Annotated

from fastapi import Depends

from .crud import activity_log_crud
from .service import ActivityLogService


def get_activity_service() -> ActivityLogService:
    return ActivityLogService(crud=activity_log_crud)


ActivityServiceDep = Annotated[ActivityLogService, Depends(get_activity_service)]
