"""ActivityLog model — append-only audit trail."""

from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base
from app.core.utils import utc_now


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    actor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_activity_logs_actor_id", "actor_id"),
        Index("ix_activity_logs_resource", "resource_type", "resource_id"),
        Index("ix_activity_logs_action", "action"),
        Index("ix_activity_logs_created_at", "created_at"),
        Index("ix_activity_logs_actor_created", "actor_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} {self.resource_type}:{self.resource_id}>"
