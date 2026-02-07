"""
Coherence Result Database Models.

SQLAlchemy models for persisting coherence calculation results.
Refers to Suite ID: TS-INT-DB-COH-001.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class CoherenceResultORM(Base):
    """
    Coherence calculation result model.

    Stores coherence scores, category breakdowns, alerts, and gaming detection.
    """

    __tablename__ = "coherence_results"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Project reference
    project_id: Mapped[UUID] = mapped_column(
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
    gaming_violations: Mapped[list[str]] = mapped_column(
        ARRAY(PGUUID(as_uuid=False)), nullable=False, default=[]
    )
    penalty_points: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_coherence_results_project_calculated", "project_id", "calculated_at"),
    )
