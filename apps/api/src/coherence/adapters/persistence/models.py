"""
Coherence Result and Clause Embedding Database Models.

SQLAlchemy models for persisting coherence calculation results and clause embeddings.
Refers to Suite ID: TS-INT-DB-COH-001.
TASK-IMPL-005: Added ClauseEmbeddingORM model for Gate 4 traceability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


def _utcnow_naive() -> datetime:
    """Return naive UTC for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class CoherenceResultORM(Base):
    """
    Coherence calculation result model.

    Stores coherence scores, category breakdowns, alerts, and gaming detection.
    """

    __tablename__ = "coherence_results"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Project reference
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Tenant reference
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Global score
    global_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        # CHECK constraint: BETWEEN 0 AND 100
    )

    # Category scores (stored as JSONB)
    # Format: {"SCOPE": 100, "BUDGET": 70, ...}
    category_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Category details with violations (stored as JSONB)
    # Format: [{"category": "SCOPE", "score": 100, "violations": []}]
    category_details: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Alerts (stored as JSONB)
    # Format: [{"rule_id": "R11", "severity": "HIGH", ...}]
    alerts: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Gaming detection
    is_gaming_detected: Mapped[bool] = mapped_column(default=False)
    gaming_violations: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=[])
    penalty_points: Mapped[int] = mapped_column(Integer, default=0)

    # Score-version audit trail — canonical 2-value enum (Phase F, ADR-009 §F)
    score_version: Mapped[str] = mapped_column(
        ENUM(
            "coherence-v1",
            "coherence-v2",
            name="coherence_score_version",
            create_type=False,
        ),
        nullable=False,
        default="coherence-v1",
        server_default="coherence-v1",
    )
    score_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_missing_dimensions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False, index=True
    )

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_coherence_results_project_calculated", "project_id", "calculated_at"),
        Index("ix_coherence_results_tenant", "tenant_id"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class ClauseEmbeddingORM(Base):
    """
    Clause embedding model for coherence engine RAG.

    Stores vector embeddings of contract clauses for similarity search.
    TASK-IMPL-005: Created ORM model for Gate 4 traceability.
    """

    __tablename__ = "clause_embeddings"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    clause_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="other")
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="SCOPE", index=True
    )
    embedding_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("clause_id", "project_id", name="uq_clause_embeddings_clause_project"),
        Index("ix_clause_embeddings_tenant", "tenant_id"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class CategoryCentroidORM(Base):
    """
    Cached prototype centroids for deterministic Category Router matching.

    Keyed by category, embedding_model, and score_version to allow seamless migration.
    This is a global reference table based on category_registry.yaml and
    does not enforce tenant isolation (RLS).
    """

    __tablename__ = "category_centroids"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    score_version: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    seed_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "category", "embedding_model", "score_version", name="uq_category_centroids_key"
        ),
    )
