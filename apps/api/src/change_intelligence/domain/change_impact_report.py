"""Evidence-gated Change-Impact Report contract for ADR-016.

TS-UT-CI-REPORT-001

Conflicts and numeric impact estimates remain honest-null in this slice.
ADR-017 owns cross-document propagation, so this report records the missing
data reason instead of fabricating impact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.change_intelligence.domain.contracts import SemanticChange
from src.evidence.domain.runtime_trust import EvidenceRef


class ChangeImpactReport(BaseModel):
    """Product-facing report assembled from L1 and optional L2 changes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: UUID
    project_id: UUID
    tenant_id: UUID
    from_revision_id: UUID
    to_revision_id: UUID
    changes: list[SemanticChange]
    conflicts: list[dict[str, object]] = Field(default_factory=list)
    impact_estimate: dict[str, object] | None = None
    insufficient_data_reasons: list[str] = Field(default_factory=list)
    overall_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    hitl_routing: Literal["auto", "needs_review"]
    created_at: datetime

    @computed_field
    def summary_counts(self) -> dict[str, int]:
        return {
            "added": sum(1 for change in self.changes if change.change_type == "added"),
            "removed": sum(1 for change in self.changes if change.change_type == "removed"),
            "modified": sum(1 for change in self.changes if change.change_type == "modified"),
            "needs_review": sum(1 for change in self.changes if change.needs_review),
        }


__all__ = ["ChangeImpactReport"]
