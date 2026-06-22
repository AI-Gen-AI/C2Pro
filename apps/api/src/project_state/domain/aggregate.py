"""FROZEN ProjectState aggregate root (ADR-014 / TASK-V3-014-01, -06).

The primary unit of intelligence (ADR-014): the Project materialized as canonical
entities derived from document revisions. Immutable value object — transitions
return new instances via ``model_copy``; persistence is handled by the repository
port (no ``commit()`` in repos).

Forward-referenced collections owned by later ADRs are intentionally NOT declared
here — they are added by their ADRs:
  change_sets   → ADR-016    health_snapshots → ADR-018    action_items → ADR-019
This keeps ADR-014 the keystone without pre-empting downstream contracts.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.project_state.domain.entities import (
    Clause,
    Obligation,
    ProjectBudgetItem,
    ProjectRisk,
    ProjectWbsActivity,
    RaciCell,
    Stakeholder,
)
from src.project_state.domain.lifecycle import LifecycleStatus


class ProjectState(BaseModel):
    """Aggregate root. Lifecycle: draft → active → superseded → archived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    tenant_id: UUID
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    document_revision_ids: list[UUID] = Field(default_factory=list)  # ADR-015

    # ── Canonical, input-derived entities ────────────────────────────────────
    clauses: list[Clause] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    risks: list[ProjectRisk] = Field(default_factory=list)
    wbs_activities: list[ProjectWbsActivity] = Field(default_factory=list)
    budget_items: list[ProjectBudgetItem] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    raci: list[RaciCell] = Field(default_factory=list)

    # ── Reserved seam: future Procurement Intelligence (canon Phase 3) — NO logic ──
    procurement_refs: list[UUID] = Field(default_factory=list)

    def with_lifecycle(self, status: LifecycleStatus) -> ProjectState:
        """Immutable lifecycle transition — returns a new aggregate."""
        return self.model_copy(update={"lifecycle_status": status})


__all__ = ["ProjectState"]
