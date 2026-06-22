"""FROZEN canonical ProjectState entities (ADR-014 / TASK-V3-014-01, -06).

Each entity is an immutable value object carrying identity, lifecycle, revision
lineage (ADR-015), and INV-1 evidence provenance. Extraction-derived entities
**compose** the frozen ADR-013 graph contracts as their ``payload`` — no field
duplication. Reserved future-domain seams (Procurement / Stakeholder Intelligence)
are nullable and carry NO logic (canon Phase 3).

Out of scope here (owned by their ADRs; the aggregate references them by id):
DocumentRevision (ADR-015), ChangeSet (ADR-016), HealthSnapshot (ADR-018),
ActionItem / ReviewCase (ADR-019/020).

FROZEN CONTRACT — do not add/rename/remove fields without re-freezing + notifying
implementers (Codex builds adapters/migration against this).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.analysis.domain.contracts import BudgetItem, RiskItem, WbsActivity
from src.evidence.domain.runtime_trust import EvidenceRef
from src.project_state.domain.lifecycle import LifecycleStatus

_ENTITY = ConfigDict(extra="forbid", frozen=True)


class ProjectEntity(BaseModel):
    """Base value object for every canonical project-state entity."""

    model_config = _ENTITY

    entity_id: UUID
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    source_revision_id: UUID | None = None  # DocumentRevision (ADR-015)
    extraction_run_id: UUID | None = None  # atomic batch supersession
    evidence: list[EvidenceRef] = Field(default_factory=list)  # INV-1 provenance


class Clause(ProjectEntity):
    clause_id: str
    text: str
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)


class Obligation(ProjectEntity):
    description: str
    clause_id: str | None = None
    due_date: str | None = None  # ISO date; schedule ingestion (ADR-018 v1) tightens later


class ProjectRisk(ProjectEntity):
    """Extraction RiskItem (ADR-013) elevated to a canonical, provenance-bearing entity."""

    payload: RiskItem


class ProjectWbsActivity(ProjectEntity):
    payload: WbsActivity


class ProjectBudgetItem(ProjectEntity):
    payload: BudgetItem


class Stakeholder(ProjectEntity):
    name: str
    role: str | None = None
    company_name: str | None = None
    is_legal_entity: bool = False
    # ── Reserved seams: future Stakeholder Intelligence (canon Phase 3) — NO logic ──
    authority_level: str | None = None
    escalation_role: str | None = None
    communication_preference: str | None = None


class RaciCell(ProjectEntity):
    stakeholder_id: UUID
    activity_code: str
    assignment: str  # "R" | "A" | "C" | "I"


__all__ = [
    "ProjectEntity",
    "Clause",
    "Obligation",
    "ProjectRisk",
    "ProjectWbsActivity",
    "ProjectBudgetItem",
    "Stakeholder",
    "RaciCell",
]
