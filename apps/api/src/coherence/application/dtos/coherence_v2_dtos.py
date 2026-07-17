"""
ECOA v2 Pydantic DTOs — canonical JSON contract for Coherence Score v2.

Source of truth: ADR-009 §5 (locked contract with TRI terminology).

Refers to Suite ID: TS-UA-COH-V2-DTO-001.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


from src.core.json_types import JsonDict, JsonValue


class CategoryStatus(str, Enum):
    PENDING_DOCUMENTS = "pending_documents"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SCORED = "scored"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    NOT_APPLICABLE = "not_applicable"
    PROCESSING_ERROR = "processing_error"


_NULL_SCORE_STATES: frozenset[CategoryStatus] = frozenset(
    {
        CategoryStatus.PENDING_DOCUMENTS,
        CategoryStatus.INSUFFICIENT_EVIDENCE,
        CategoryStatus.NOT_APPLICABLE,
        CategoryStatus.PROCESSING_ERROR,
    }
)


class ScoreExplanation(BaseModel):
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    dominant_rules: list[str] = Field(default_factory=list)
    score_path: list[JsonDict] = Field(default_factory=list)


class BudgetReconciliation(BaseModel):
    """TASK-BCK-093: Typed reconciliation fields from DET-BUD FindingSignal.raw_data."""

    items_sum: float
    stated_total: float | None = None
    contract_total: float | None = None
    deviation_pct: float
    direction: str


class CategoryV2(BaseModel):
    category: str
    status: CategoryStatus
    coherence_score: float | None = None
    evidence_coverage: float = 0.0
    technical_reliability: float = 0.0
    evidence_freshness: float = 0.0
    applicability_reason: str | None = None
    score_explanation: ScoreExplanation | None = None
    evidence_count: int = 0
    evidence_references: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    detected_conflicts: list[JsonDict] = Field(default_factory=list)
    rationale: str | None = None
    recommendation: str | None = None
    calculation_metadata: JsonDict = Field(default_factory=dict)
    budget_reconciliation: BudgetReconciliation | None = None

    @model_validator(mode="after")
    def _null_score_when_no_evidence(self) -> CategoryV2:
        if self.status in _NULL_SCORE_STATES and self.coherence_score is not None:
            raise ValueError(f"coherence_score must be None when status={self.status.value!r}")
        return self


class GlobalV2(BaseModel):
    coherence_score: float | None = None
    completeness_score: float = 0.0
    technical_reliability_index: float = 0.0
    status: Literal["scored", "partial", "insufficient_active_weight", "pending_documents"]
    score_reason: str | None = None
    active_weight: float = 0.0


class CoherenceV2Payload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: UUID
    version: Literal["coherence-v2"] = "coherence-v2"
    generated_at: datetime
    global_: GlobalV2 = Field(alias="global")
    categories: list[CategoryV2] = Field(default_factory=list)


__all__ = [
    "BudgetReconciliation",
    "CategoryStatus",
    "CategoryV2",
    "CoherenceV2Payload",
    "GlobalV2",
    "ScoreExplanation",
]
