"""SnapshotWriter application service (ADR-015 / TASK-V3-015-05).

TS-UT-TSW-001
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.project_state.domain.aggregate import ProjectState
from src.project_state.ports.project_state_repository import ProjectStateRepository
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger
from src.temporal.ports.project_snapshot_repository import IProjectSnapshotRepository

_SNAPSHOT_EPOCH = datetime(1970, 1, 1)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SnapshotWriter:
    """Writes honest, lightweight project snapshots without owning transactions."""

    def __init__(
        self,
        project_state_repository: ProjectStateRepository,
        snapshot_repository: IProjectSnapshotRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._project_state_repository = project_state_repository
        self._snapshot_repository = snapshot_repository
        self._clock = clock or _utcnow

    async def write_snapshot(
        self,
        project_id: UUID,
        tenant_id: UUID,
        trigger: SnapshotTrigger,
        source_event_id: UUID | None = None,
    ) -> ProjectSnapshot:
        now = self._clock()
        existing = await self._find_existing_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=trigger,
            captured_at=now,
            source_event_id=source_event_id,
        )
        if existing is not None:
            return existing

        state = await self._project_state_repository.get(project_id, tenant_id)
        counts = self._counts(state)
        totals = self._totals(state)
        snapshot = ProjectSnapshot(
            snapshot_id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            captured_at=now,
            trigger=trigger,
            health_vector={"status": "pending_health_engine"},
            coherence_subscore=None,
            counts=counts,
            totals=totals,
            source_event_id=source_event_id,
            created_at=now,
        )
        return await self._snapshot_repository.append_snapshot(snapshot)

    async def _find_existing_snapshot(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        trigger: SnapshotTrigger,
        captured_at: datetime,
        source_event_id: UUID | None,
    ) -> ProjectSnapshot | None:
        if source_event_id is not None:
            snapshots = await self._snapshot_repository.list_since(
                project_id, tenant_id, _SNAPSHOT_EPOCH
            )
            for snapshot in snapshots:
                if snapshot.source_event_id == source_event_id:
                    return snapshot

        if trigger is SnapshotTrigger.SCHEDULED:
            day_start = captured_at.replace(hour=0, minute=0, second=0, microsecond=0)
            snapshots = await self._snapshot_repository.list_since(project_id, tenant_id, day_start)
            for snapshot in snapshots:
                if snapshot.trigger is SnapshotTrigger.SCHEDULED:
                    return snapshot
        return None

    @staticmethod
    def _counts(state: ProjectState | None) -> dict[str, int]:
        if state is None:
            return {
                "clauses": 0,
                "obligations": 0,
                "risks": 0,
                "wbs_activities": 0,
                "budget_items": 0,
                "stakeholders": 0,
                "raci": 0,
            }
        return {
            "clauses": len(state.clauses),
            "obligations": len(state.obligations),
            "risks": len(state.risks),
            "wbs_activities": len(state.wbs_activities),
            "budget_items": len(state.budget_items),
            "stakeholders": len(state.stakeholders),
            "raci": len(state.raci),
        }

    @staticmethod
    def _totals(state: ProjectState | None) -> dict[str, object]:
        if state is None:
            return {"budget_amount": 0.0, "budget_amount_by_currency": {}}

        by_currency: dict[str, float] = {}
        for item in state.budget_items:
            amount = float(item.payload.amount)
            currency = item.payload.currency
            by_currency[currency] = by_currency.get(currency, 0.0) + amount
        return {
            "budget_amount": sum(by_currency.values()),
            "budget_amount_by_currency": by_currency,
        }
