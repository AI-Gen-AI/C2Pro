"""ORM model for the HITL review queue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ReviewItemORM(Base):
    __tablename__ = "review_items"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    item_type: Mapped[str] = mapped_column(String(128), nullable=False)
    current_status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(
            ReviewStatus,
            values_callable=lambda obj: [e.value for e in obj],
            name="reviewstatus",
        ),
        nullable=False,
        default=ReviewStatus.DRAFT,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    impact_level: Mapped[ImpactLevel] = mapped_column(
        SQLEnum(
            ImpactLevel,
            values_callable=lambda obj: [e.value for e in obj],
            name="impactlevel",
        ),
        nullable=False,
        default=ImpactLevel.LOW,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    approved_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    item_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    review_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # TASK-BCK-024: Checkpoint tracking for LangGraph workflow resumption
    checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    review_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_decision: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now_naive, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now_naive, onupdate=_utc_now_naive, nullable=False,
    )

    __table_args__ = (
        Index("ix_review_items_tenant_status", "tenant_id", "current_status"),
        Index("ix_review_items_sla_due", "sla_due_date"),
        # TASK-BCK-024: Indexes for checkpoint tracking
        Index("ix_review_items_checkpoint_id", "checkpoint_id"),
        Index("ix_review_items_thread_id", "thread_id"),
        Index("ix_review_items_project_status", "project_id", "current_status"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


# TASK-BCK-025: Notification configuration model
class NotificationConfigModel(Base):
    """Per-tenant notification configuration."""

    __tablename__ = "notification_configs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    notification_channels: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    email_recipients: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    slack_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_headers: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now_naive, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now_naive, onupdate=_utc_now_naive, nullable=False
    )

    __table_args__ = ({"info": {"rls_policy": "tenant_isolation"}},)
