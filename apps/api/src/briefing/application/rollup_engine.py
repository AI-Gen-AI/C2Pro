"""Pure portfolio R/A/G rollup engine (ADR-021, TASK-V3-021-03).

Thresholds: overall >= 0.7 → GREEN, >= 0.4 → AMBER, < 0.4 → RED.
All figures derive from the latest snapshot per project.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.briefing.domain.rollup import PortfolioRollup, ProjectRollupEntry, RagStatus
from src.temporal.domain.project_snapshot import ProjectSnapshot

_GREEN_THRESHOLD = 0.7
_AMBER_THRESHOLD = 0.4


def _rag_for(overall: float) -> RagStatus:
    if overall >= _GREEN_THRESHOLD:
        return RagStatus.GREEN
    if overall >= _AMBER_THRESHOLD:
        return RagStatus.AMBER
    return RagStatus.RED


class RollupEngine:
    """Stateless engine that produces a PortfolioRollup from per-project snapshot lists."""

    @staticmethod
    def compute(
        snapshots_by_project: dict[UUID, list[ProjectSnapshot]],
        *,
        tenant_id: UUID | None = None,
    ) -> PortfolioRollup:
        entries: list[ProjectRollupEntry] = []

        for project_id, snaps in snapshots_by_project.items():
            if not snaps:
                continue
            ordered = sorted(snaps, key=lambda s: s.captured_at)
            latest = ordered[-1]
            overall = float(latest.health_vector.get("overall", 0.0))
            entries.append(
                ProjectRollupEntry(
                    project_id=project_id,
                    rag_status=_rag_for(overall),
                    overall_health=overall,
                    open_action_items=int(latest.counts.get("open_action_items", 0)),
                    snapshot_count=len(ordered),
                    latest_snapshot_at=latest.captured_at,
                )
            )

        if tenant_id is not None:
            resolved_tenant: UUID | None = tenant_id
        else:
            first_snaps = next(iter(snapshots_by_project.values()), [])
            resolved_tenant = first_snaps[0].tenant_id if first_snaps else None

        return PortfolioRollup(
            tenant_id=resolved_tenant or UUID(int=0),
            generated_at=datetime.now(tz=UTC),
            entries=tuple(entries),
        )


__all__ = ["RollupEngine"]
