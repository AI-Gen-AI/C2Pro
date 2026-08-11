"""Pure projection engine: snapshot list → MorningBriefingProjection (ADR-021)."""

from __future__ import annotations

from datetime import UTC, datetime

from src.briefing.domain.projection import HealthDelta, MorningBriefingProjection
from src.temporal.domain.project_snapshot import ProjectSnapshot


class ProjectionEngine:
    """Stateless engine that folds a list of snapshots into a briefing projection."""

    @staticmethod
    def project(snapshots: list[ProjectSnapshot]) -> MorningBriefingProjection:
        if not snapshots:
            raise ValueError("project() requires at least one snapshot")

        ordered = sorted(snapshots, key=lambda s: s.captured_at)
        first = ordered[0]
        last = ordered[-1]

        health_deltas = ProjectionEngine._compute_health_deltas(first, last) if len(ordered) > 1 else ()

        new_action_item_count = int(last.counts.get("open_action_items", 0)) - int(
            first.counts.get("open_action_items", 0)
        )
        overdue_review_count = int(last.counts.get("overdue_reviews", 0))

        trigger_events = tuple(dict.fromkeys(s.trigger.value for s in ordered))
        evidence_refs = tuple(str(s.snapshot_id) for s in ordered)

        return MorningBriefingProjection(
            project_id=first.project_id,
            snapshot_from_id=first.snapshot_id if len(ordered) > 1 else None,
            snapshot_to_id=last.snapshot_id,
            period_start=first.captured_at,
            period_end=last.captured_at,
            generated_at=datetime.now(tz=UTC),
            health_deltas=health_deltas,
            new_action_item_count=new_action_item_count,
            overdue_review_count=overdue_review_count,
            trigger_events=trigger_events,
            evidence_refs=evidence_refs,
        )

    @staticmethod
    def _compute_health_deltas(
        first: ProjectSnapshot, last: ProjectSnapshot
    ) -> tuple[HealthDelta, ...]:
        all_dims = set(first.health_vector.keys()) | set(last.health_vector.keys())
        return tuple(
            HealthDelta(
                dimension=dim,
                previous=float(first.health_vector.get(dim, 0.0)),
                current=float(last.health_vector.get(dim, 0.0)),
            )
            for dim in sorted(all_dims)
        )


__all__ = ["ProjectionEngine"]
