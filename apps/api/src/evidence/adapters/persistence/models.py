"""
Evidence Intelligence Layer persistence models (ADR-011 Phase 2A.3).

SQLAlchemy ORM for the shadow-mode evidence tables. Mirrors the declarative
Mapped[] style and naive-UTC timestamps used across the codebase
(see src/coherence/adapters/persistence/models.py).

Two tables, matching the adapter's three output channels:
  * EvidenceClaimORM             — claims channel
  * EvidenceExtractionEventORM   — processing_error + out_of_scope channels,
                                   discriminated by event_type

Refers to Suite ID: TS-INT-DB-EVI-SHADOW-001.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


def _utcnow_naive() -> datetime:
    """Return naive UTC for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class EvidenceClaimORM(Base):
    """Validated EvidenceClaim persisted in shadow mode (lifecycle_status='shadow').

    Write-only in Phase 2A.3: the Coherence Engine must not read this table yet.
    """

    __tablename__ = "evidence_claims"

    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )

    # Tenancy (RLS columns; policies deferred to 2A.5)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )

    # Claim core
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Technical axis
    algorithmic_certainty: Mapped[float] = mapped_column(nullable=False)
    freshness: Mapped[float] = mapped_column(nullable=False)

    # Verification (CVC result)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Lifecycle
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="shadow", server_default="shadow"
    )

    # SourceRef (text_anchor)
    locator_quality: Mapped[str] = mapped_column(String(32), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=_utcnow_naive
    )

    __table_args__ = (
        Index(
            "ix_claims_tenancy_doc_run",
            "tenant_id",
            "project_id",
            "document_id",
            "extraction_run_id",
        ),
        Index("ix_claims_doc_lifecycle", "document_id", "lifecycle_status"),
        CheckConstraint(
            "dimension IN ('SCOPE','BUDGET','TIME','TECHNICAL','LEGAL','QUALITY')",
            name="ck_claims_dimension",
        ),
        CheckConstraint(
            "verification_status IN "
            "('verified','uncertain','unsupported','fabrication_suspected')",
            name="ck_claims_verification_status",
        ),
        CheckConstraint(
            "locator_quality IN ('exact','approximate','missing')",
            name="ck_claims_locator_quality",
        ),
        CheckConstraint(
            "lifecycle_status IN ('shadow','active','superseded','discarded')",
            name="ck_claims_lifecycle_status",
        ),
        CheckConstraint(
            "algorithmic_certainty >= 0 AND algorithmic_certainty <= 1",
            name="ck_claims_certainty_range",
        ),
        CheckConstraint(
            "freshness >= 0 AND freshness <= 1",
            name="ck_claims_freshness_range",
        ),
    )


class EvidenceExtractionEventORM(Base):
    """Non-claim channels (processing_error / out_of_scope), discriminated by
    event_type. Typed columns for queryable diagnostics; payload_trace JSONB
    only for the variable error/drift detail."""

    __tablename__ = "evidence_extraction_events"

    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    claim_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=_utcnow_naive
    )

    __table_args__ = (
        Index("ix_events_diagnostic", "tenant_id", "event_type", "reason"),
        Index("ix_events_doc_run", "document_id", "extraction_run_id"),
        CheckConstraint(
            "event_type IN ('processing_error','out_of_scope')",
            name="ck_events_event_type",
        ),
    )
