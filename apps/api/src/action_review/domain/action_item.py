"""
ActionItem domain model (ADR-019).

Immutable Pydantic models; no SQLAlchemy or infrastructure concerns here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.evidence.domain.runtime_trust import EvidenceRef


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactArea(StrEnum):
    CONTRACT = "contract"
    SCHEDULE = "schedule"
    COST = "cost"
    RISK = "risk"
    GOVERNANCE = "governance"


class ActionStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class ObjectType(StrEnum):
    CLAUSE = "clause"
    WBS_NODE = "wbs_node"
    MILESTONE = "milestone"
    BUDGET_ITEM = "budget_item"
    RISK = "risk"
    STAKEHOLDER = "stakeholder"


class ProjectObjectRef(BaseModel):
    """Typed reference to a domain object within a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obj_type: ObjectType
    obj_id: UUID


class ActionItem(BaseModel):
    """
    A correlated, owned action derived from one or more findings.

    Created by the correlation engine; never mutated after creation.
    Reflects the ADR-019 required fields exactly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    severity: Severity
    confidence: float
    impact_area: list[ImpactArea]
    affected_objects: list[ProjectObjectRef]
    evidence_refs: list[EvidenceRef]
    recommended_action: str
    owner_stakeholder_id: UUID | None
    due_at: datetime | None
    escalation_path: list[UUID]
    correlation_group: UUID
    status: ActionStatus


__all__ = [
    "ActionItem",
    "ActionStatus",
    "EvidenceRef",
    "ImpactArea",
    "ObjectType",
    "ProjectObjectRef",
    "Severity",
]
