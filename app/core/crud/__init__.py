"""
app.core.crud — public API for the crud package.

All symbols are re-exported here so every existing import stays valid:

    from app.core.crud import CRUDBase
    from app.core.crud import CRUDBase, apply_sorting
    from app.core.crud import CRUDBase, paginated_select
    from app.core.crud import apply_sorting
"""

from app.core.crud.base import (
    CRUDBase,
    CreateSchemaType,
    ModelType,
    UpdateSchemaType,
)
from app.core.crud.helpers import apply_sorting, paginated_select

__all__ = [
    # Base class + type vars
    "CRUDBase",
    "ModelType",
    "CreateSchemaType",
    "UpdateSchemaType",
    # Query helpers
    "apply_sorting",
    "paginated_select",
]
