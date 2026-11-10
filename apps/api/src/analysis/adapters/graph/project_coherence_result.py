"""Typed ProjectGraph coherence summary for ADR-017.

TS-UT-ADR017-XDOC-001
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProjectCoherenceResult(BaseModel):
    """Small, frozen ProjectGraph read slot for cross-document coherence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    category_scores: dict[str, float | None] = Field(default_factory=dict)
    signal_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    artifact_count: int = Field(ge=0)
    llm_on: bool
    insufficient_data_reasons: list[str] = Field(default_factory=list)
    score_reason: str | None = None
    # Excluded proposed N4 risks are never equivalent to 'no risks detected'.
    excluded_risk_count: int = Field(default=0, ge=0)
    excluded_risk_reasons: dict[str, int] = Field(default_factory=dict)


__all__ = ["ProjectCoherenceResult"]
