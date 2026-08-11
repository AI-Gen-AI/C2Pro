"""
Correlation engine for ActionItems (ADR-019).

Applies two rules (group-by-revision, group-by-shared-entity) using a
union-find structure so transitive merges work correctly. Pure function —
no I/O, no state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.action_review.domain.action_item import (
    ActionItem,
    ActionStatus,
    ImpactArea,
    ObjectType,
    ProjectObjectRef,
    Severity,
)
from src.evidence.domain.runtime_trust import EvidenceRef


@dataclass(frozen=True)
class CorrelationInput:
    """
    Pre-ActionItem data produced by the analysis pipeline.

    One CorrelationInput maps to one ActionItem after the engine runs.
    """

    finding_id: UUID
    revision_id: UUID | None
    object_refs: list[ProjectObjectRef]
    severity: Severity
    confidence: float
    impact_area: list[ImpactArea]
    recommended_action: str
    evidence_refs: list[EvidenceRef]
    owner_stakeholder_id: UUID | None
    due_at: datetime | None
    escalation_path: list[UUID]


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]  # path compression
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def correlate(findings: list[CorrelationInput]) -> list[ActionItem]:
    """
    Apply correlation rules and return one ActionItem per input finding.

    Rules applied (both via union-find so transitive merges work):
    1. group-by-revision: same revision_id → same group.
    2. group-by-shared-entity: share ≥1 (obj_type, obj_id) pair → same group.
    """
    if not findings:
        return []

    uf = _UnionFind(len(findings))

    # Rule 1: group-by-revision
    revision_to_first: dict[UUID, int] = {}
    for i, f in enumerate(findings):
        if f.revision_id is not None:
            if f.revision_id in revision_to_first:
                uf.union(revision_to_first[f.revision_id], i)
            else:
                revision_to_first[f.revision_id] = i

    # Rule 2: group-by-shared-entity
    entity_to_first: dict[tuple[ObjectType, UUID], int] = {}
    for i, f in enumerate(findings):
        for ref in f.object_refs:
            key = (ref.obj_type, ref.obj_id)
            if key in entity_to_first:
                uf.union(entity_to_first[key], i)
            else:
                entity_to_first[key] = i

    # Assign stable group UUIDs per root (deterministic: derived from finding_id of root)
    root_to_group: dict[int, UUID] = {}
    for i, _f in enumerate(findings):
        root = uf.find(i)
        if root not in root_to_group:
            root_to_group[root] = uuid.uuid5(uuid.NAMESPACE_URL, str(findings[root].finding_id))

    return [
        ActionItem(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"action:{f.finding_id}"),
            severity=f.severity,
            confidence=f.confidence,
            impact_area=f.impact_area,
            affected_objects=f.object_refs,
            evidence_refs=f.evidence_refs,
            recommended_action=f.recommended_action,
            owner_stakeholder_id=f.owner_stakeholder_id,
            due_at=f.due_at,
            escalation_path=f.escalation_path,
            correlation_group=root_to_group[uf.find(i)],
            status=ActionStatus.OPEN,
        )
        for i, f in enumerate(findings)
    ]


__all__ = ["CorrelationInput", "correlate"]
