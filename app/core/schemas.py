"""Reusable Pydantic schema bases for list/pagination endpoints.

Layer: Cross-cutting — imported by every module that exposes list endpoints.
       (PROJECT_CONVENTIONS §3.1 — `app/core/` is reusable, never project-specific.)

Responsibility:
  - ListParams: base schema carrying the universal list-endpoint params
    (skip / limit / sort_by / sort_order). Concrete modules subclass this
    and add their own filter fields, narrowing ``sort_by`` to a Literal[...]
    of their actual sortable columns so OpenAPI exposes a typed dropdown
    and invalid values are rejected at the route layer (FastAPI 422) instead
    of being silently mapped to the default in CRUD.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SortOrder = Literal["asc", "desc"]


class ListParams(BaseModel):
    """Common pagination + sort parameters for list endpoints.

    Subclass and override ``sort_by`` with a ``Literal["..."]`` of the
    columns this resource actually allows sorting by, e.g.

        class LeadListParams(ListParams):
            sort_by: Optional[Literal["created_at", "updated_at", "relevance"]] = None
            ... module-specific filters ...
    """

    model_config = ConfigDict(extra="ignore")

    skip: int = Field(0, ge=0, description="Number of records to skip.")
    limit: int = Field(
        100, ge=1, le=500, description="Maximum number of records to return."
    )
    sort_by: Optional[str] = Field(
        None, description="Column name to sort by. Resource-specific."
    )
    sort_order: SortOrder = Field(
        "desc", description="Sort direction: asc or desc."
    )


__all__ = ["ListParams", "SortOrder"]
