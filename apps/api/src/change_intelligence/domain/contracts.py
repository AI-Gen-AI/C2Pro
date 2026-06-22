"""Typed ChangeSet contracts for ADR-016 L1 structural diff.

TS-UT-CI-CON-001

L1 intentionally leaves severity and confidence as None. Those fields belong
to L2 semantic analysis; structural-only diffing must not fabricate impact or
certainty beyond anchor-resolution confidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.evidence.domain.runtime_trust import EvidenceRef

ObjectType = Literal["clause", "milestone", "budget_item", "rfi", "change_order"]
ChangeType = Literal[
    "added",
    "removed",
    "modified",
    "superseded",
    "conflict_introduced",
]
Severity = Literal["info", "low", "medium", "high", "critical"]


class SemanticChange(BaseModel):
    """One evidence-gated object-level change."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_type: ObjectType
    change_type: ChangeType
    anchor: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    semantic_summary: str
    match_confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    severity: Severity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ChangeSet(BaseModel):
    """Structural-only contract revision change set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    changeset_id: UUID
    project_id: UUID
    tenant_id: UUID
    from_revision_id: UUID
    to_revision_id: UUID
    object_scope: Literal["contract"] = "contract"
    layer: Literal["L1"] = "L1"
    changes: list[SemanticChange] = Field(default_factory=list)
    created_at: datetime

    @computed_field
    @property
    def summary_counts(self) -> dict[str, int]:
        return {
            "added": sum(1 for change in self.changes if change.change_type == "added"),
            "removed": sum(1 for change in self.changes if change.change_type == "removed"),
            "modified": sum(1 for change in self.changes if change.change_type == "modified"),
            "needs_review": sum(1 for change in self.changes if change.needs_review),
        }


__all__ = ["ChangeSet", "SemanticChange"]
