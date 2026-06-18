"""TS-UD-HEALTH-018-001 - Frozen health vector contracts for ADR-018.

L1 health contracts keep composite score and trend honest-null until ADR-018
Slice 5 computes them from snapshots. Dimension severity is represented by
score/band, while confidence remains a separate evidence-quality axis.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.evidence.domain.runtime_trust import EvidenceRef

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)


class HealthDimension(str, Enum):
    CONTRACT = "contract"
    RISK = "risk"
    DOCUMENTATION = "documentation"
    GOVERNANCE = "governance"
    SCHEDULE = "schedule"
    COST = "cost"
    DELIVERABLES = "deliverables"


class HealthBand(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthTrend(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class HealthNullReason(str, Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"
    BUDGET_EXHAUSTED = "budget_exhausted"


def band_for_score(score: float | None) -> HealthBand:
    """Map a 0-100 health score to the product health band."""

    if score is None:
        return HealthBand.UNKNOWN
    if score >= 80:
        return HealthBand.HEALTHY
    if score >= 60:
        return HealthBand.WATCH
    if score >= 40:
        return HealthBand.AT_RISK
    return HealthBand.CRITICAL


class HealthSignal(BaseModel):
    """One dimension's health result.

    A non-null score must be backed by concrete evidence. Confidence remains a
    separate evidence-quality axis and cannot substitute for provenance.
    """

    model_config = _FROZEN_CONTRACT

    dimension: HealthDimension
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    band: HealthBand
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    trend: HealthTrend = HealthTrend.UNKNOWN
    missing_data: list[str] = Field(default_factory=list)
    null_reason: HealthNullReason | None = None

    @model_validator(mode="after")
    def _enforce_honest_null_invariants(self) -> HealthSignal:
        expected_band = band_for_score(self.score)
        if self.score is None:
            if self.band is not HealthBand.UNKNOWN:
                raise ValueError("null health score requires UNKNOWN band")
            if self.null_reason is None:
                raise ValueError("null health score requires a null_reason")
            return self

        if self.band is not expected_band:
            raise ValueError("health band must match score")
        if self.null_reason is not None:
            raise ValueError("non-null health score cannot carry a null_reason")
        if not self.evidence:
            raise ValueError("non-null health score requires supporting evidence")
        return self


class HealthVector(BaseModel):
    """Project-level health vector across supported dimensions."""

    model_config = _FROZEN_CONTRACT

    project_id: UUID
    tenant_id: UUID
    dimensions: list[HealthSignal]
    composite_score: float | None = Field(default=None, ge=0.0, le=100.0)
    composite_band: HealthBand = HealthBand.UNKNOWN
    computed_at: datetime


__all__ = [
    "HealthBand",
    "HealthDimension",
    "HealthNullReason",
    "HealthSignal",
    "HealthTrend",
    "HealthVector",
    "band_for_score",
]
