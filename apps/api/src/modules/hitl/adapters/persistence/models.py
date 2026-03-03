"""ORM model for the HITL review queue."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


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
    item_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    __table_args__ = (
        Index("ix_review_items_tenant_status", "tenant_id", "current_status"),
        Index("ix_review_items_sla_due", "sla_due_date"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )
