"""TS-UD-HEALTH-018-001 - Frozen health vector contracts for ADR-018.

L1 health contracts keep composite score and trend honest-null until ADR-018
Slice 5 computes them from snapshots. Dimension severity is represented by
score/band, while confidence remains a separate evidence-quality axis.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.evidence.domain.runtime_trust import EvidenceRef
from src.health.domain.contract_clarity import ContractClarityFinding
from src.health.domain.null_reason import HealthNullReason
from src.health.domain.single_document_coverage import (
    EvidenceGranularity,
    SingleDocumentCoverage,
)

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)


class HealthDimension(StrEnum):
    CONTRACT = "contract"
    RISK = "risk"
    DOCUMENTATION = "documentation"
    GOVERNANCE = "governance"
    SCHEDULE = "schedule"
    COST = "cost"
    DELIVERABLES = "deliverables"


class HealthBand(StrEnum):
    HEALTHY = "healthy"
    WATCH = "watch"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthTrend(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


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
    composite_trend: HealthTrend = HealthTrend.UNKNOWN
    computed_at: datetime
    # ADR-022 (V3-P1-SCOPE-11): findings-only, never rolled into a dimension
    # score or composite_score. See health.domain.contract_clarity.
    contract_clarity_findings: list[ContractClarityFinding] = Field(default_factory=list)
    # ADR-024 (P0b L4-3): the single-document product surface — six category
    # assessments, findings, factual missing_data, actionable gaps and preserved
    # CROSS findings. Same discipline as contract_clarity_findings: carried here but
    # NEVER rolled into a dimension score or composite_score.
    # ``None`` means the assessment is UNAVAILABLE / NOT EVALUATED for this snapshot
    # (legacy analysis, or no assessment ever produced) — it never means "empty".
    single_document_coverage: SingleDocumentCoverage | None = None
    # P0b-R1: what the coverage's ``evidence_clause_ids`` identify — persisted
    # ``documents.clauses`` UUIDs, or one synthetic document-level marker. Carried
    # explicitly so no consumer has to infer it from the shape of an id.
    single_document_evidence_granularity: EvidenceGranularity | None = None

    @model_validator(mode="after")
    def _enforce_granularity_pairing(self) -> HealthVector:
        """Coverage and its granularity travel together, or neither is present.

        Coverage with no granularity would leave every evidence id unqualified;
        granularity with no coverage would qualify nothing. Both states are
        meaningless, so both are rejected rather than silently tolerated.
        """
        if self.single_document_coverage is None:
            if self.single_document_evidence_granularity is not None:
                raise ValueError(
                    "single_document_evidence_granularity requires single_document_coverage"
                )
        elif self.single_document_evidence_granularity is None:
            raise ValueError(
                "single_document_coverage requires single_document_evidence_granularity"
            )
        return self


__all__ = [
    "EvidenceGranularity",
    "HealthBand",
    "HealthDimension",
    "HealthNullReason",
    "HealthSignal",
    "HealthTrend",
    "HealthVector",
    "band_for_score",
]
