"""Read-model projections for morning briefing (ADR-021, TASK-V3-021-01).

Invariant: these models are derived exclusively from ProjectSnapshot history.
They represent no new source of truth — every field traces back to evidence_refs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class HealthDelta:
    """Per-dimension health change between two snapshots."""

    dimension: str
    previous: float
    current: float

    @property
    def delta(self) -> float:
        return self.current - self.previous


@dataclass(frozen=True)
class MorningBriefingProjection:
    """Materialized read-model projection of snapshot deltas for a morning briefing.

    All numeric fields are evidence-backed (INV-1): each figure derives
    from the snapshots referenced in evidence_refs.
    """

    project_id: UUID
    snapshot_from_id: UUID | None
    snapshot_to_id: UUID
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    health_deltas: tuple[HealthDelta, ...]
    new_action_item_count: int
    overdue_review_count: int
    trigger_events: tuple[str, ...]
    evidence_refs: tuple[str, ...]


__all__ = ["HealthDelta", "MorningBriefingProjection"]
