"""ORM model for the HITL review queue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
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


class ResumeOperationORM(Base):
    """V3 durable lifecycle of one HITL resume, per EXACT review row.

    C2PRO P0b crash-safe HITL resume V3. The application drives this table
    through explicit compare-and-set statements (adapters/persistence/
    resume_ownership.py) rather than the ORM, because ownership transitions
    must be single atomic UPDATEs guarded by the exact attempt/owner/fence
    they expect, timed by PostgreSQL's clock_timestamp(). The mapping exists
    so the table is part of the metadata the test schema is built from and
    so it is introspectable with the rest of the module.
    """

    __tablename__ = "resume_operations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    review_row_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # The IMMUTABLE human-interrupt checkpoint: the only one a new attempt
    # may restart from.
    source_checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    terminal_checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_attempt_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    owner_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    decision_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phase: Mapped[str] = mapped_column(String(40), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    analysis_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    operation_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now_naive
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now_naive
    )

    __table_args__ = (
        Index("uq_resume_operations_review_row", "review_row_id", unique=True),
        Index("ix_resume_operations_phase_next_attempt", "phase", "next_attempt_at"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class ResumeOperationAttemptORM(Base):
    """Append-only ownership/decision ledger for resume operations.

    One immutable row per attempt. A takeover or a changed decision creates
    a NEW attempt rather than mutating the old one, so the fence history and
    which checkpoints belong to which attempt stay auditable.
    """

    __tablename__ = "resume_operation_attempts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    operation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resume_operations.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_token: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decision_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    terminal_checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now_naive
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # The fence is monotonic per operation: two attempts can never share one.
        Index(
            "uq_resume_attempts_operation_fence",
            "operation_id",
            "fencing_token",
            unique=True,
        ),
        {"info": {"rls_policy": "tenant_isolation"}},
    )
