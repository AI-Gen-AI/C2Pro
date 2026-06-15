"""Tests for SnapshotWriter application service (ADR-015 / TASK-V3-015-05)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.contracts import BudgetItem, RiskItem, WbsActivity
from src.project_state.domain.aggregate import ProjectState
from src.project_state.domain.entities import (
    Clause,
    ProjectBudgetItem,
    ProjectRisk,
    ProjectWbsActivity,
    Stakeholder,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger


def _now() -> datetime:
    return datetime(2026, 6, 16, 9, 0, 0)


class _ProjectStateRepo:
    def __init__(self, state: ProjectState | None) -> None:
        self.state = state

    async def get(self, project_id: UUID, tenant_id: UUID) -> ProjectState | None:
        if self.state and self.state.project_id == project_id and self.state.tenant_id == tenant_id:
            return self.state
        return None


class _SnapshotRepo:
    def __init__(self, existing: list[ProjectSnapshot] | None = None) -> None:
        self.snapshots = list(existing or [])

    async def append_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        self.snapshots.append(snapshot)
        return snapshot

    async def latest(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None:
        matches = [
            snapshot
            for snapshot in self.snapshots
            if snapshot.project_id == project_id and snapshot.tenant_id == tenant_id
        ]
        return max(matches, key=lambda snapshot: snapshot.captured_at) if matches else None

    async def list_since(
        self, project_id: UUID, tenant_id: UUID, since: datetime
    ) -> list[ProjectSnapshot]:
        return [
            snapshot
            for snapshot in self.snapshots
            if snapshot.project_id == project_id
            and snapshot.tenant_id == tenant_id
            and snapshot.captured_at >= since
        ]


def _state(project_id: UUID, tenant_id: UUID) -> ProjectState:
    return ProjectState(
        project_id=project_id,
        tenant_id=tenant_id,
        clauses=[Clause(entity_id=uuid4(), clause_id="C-1", text="Scope")],
        risks=[
            ProjectRisk(
                entity_id=uuid4(),
                payload=RiskItem(title="Risk", description="Risk desc"),
            )
        ],
        wbs_activities=[
            ProjectWbsActivity(
                entity_id=uuid4(),
                payload=WbsActivity(code="W-1", name="Work"),
            )
        ],
        budget_items=[
            ProjectBudgetItem(
                entity_id=uuid4(),
                payload=BudgetItem(name="Concrete", amount=10.5, currency="EUR"),
            ),
            ProjectBudgetItem(
                entity_id=uuid4(),
                payload=BudgetItem(name="Steel", amount=4.5, currency="EUR"),
            ),
        ],
        stakeholders=[Stakeholder(entity_id=uuid4(), name="Owner")],
    )


@pytest.mark.asyncio
async def test_snapshot_writer_assembles_counts_totals_and_placeholder_health() -> None:
    from src.temporal.application.snapshot_writer import SnapshotWriter

    project_id = uuid4()
    tenant_id = uuid4()
    snapshot_repo = _SnapshotRepo()
    writer = SnapshotWriter(
        project_state_repository=_ProjectStateRepo(_state(project_id, tenant_id)),
        snapshot_repository=snapshot_repo,
        clock=_now,
    )

    snapshot = await writer.write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.REVISION_INGESTED,
    )

    assert snapshot.health_vector == {"status": "pending_health_engine"}
    assert snapshot.counts == {
        "clauses": 1,
        "obligations": 0,
        "risks": 1,
        "wbs_activities": 1,
        "budget_items": 2,
        "stakeholders": 1,
        "raci": 0,
    }
    assert snapshot.totals == {"budget_amount": 15.0, "budget_amount_by_currency": {"EUR": 15.0}}
    assert snapshot_repo.snapshots == [snapshot]


@pytest.mark.asyncio
async def test_snapshot_writer_skips_duplicate_source_event_id() -> None:
    from src.temporal.application.snapshot_writer import SnapshotWriter

    project_id = uuid4()
    tenant_id = uuid4()
    source_event_id = uuid4()
    existing = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=_now(),
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        health_vector={"status": "pending_health_engine"},
        source_event_id=source_event_id,
        created_at=_now(),
    )
    snapshot_repo = _SnapshotRepo([existing])
    writer = SnapshotWriter(
        project_state_repository=_ProjectStateRepo(_state(project_id, tenant_id)),
        snapshot_repository=snapshot_repo,
        clock=_now,
    )

    snapshot = await writer.write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=source_event_id,
    )

    assert snapshot is existing
    assert snapshot_repo.snapshots == [existing]


@pytest.mark.asyncio
async def test_snapshot_writer_skips_duplicate_scheduled_snapshot_for_same_day() -> None:
    from src.temporal.application.snapshot_writer import SnapshotWriter

    project_id = uuid4()
    tenant_id = uuid4()
    existing = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=_now(),
        trigger=SnapshotTrigger.SCHEDULED,
        health_vector={"status": "pending_health_engine"},
        created_at=_now(),
    )
    snapshot_repo = _SnapshotRepo([existing])
    writer = SnapshotWriter(
        project_state_repository=_ProjectStateRepo(_state(project_id, tenant_id)),
        snapshot_repository=snapshot_repo,
        clock=lambda: datetime(2026, 6, 16, 18, 0, 0),
    )

    snapshot = await writer.write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.SCHEDULED,
    )

    assert snapshot is existing
    assert snapshot_repo.snapshots == [existing]


def test_snapshot_writer_source_has_no_commit_call() -> None:
    import pathlib
    import re

    path = (
        pathlib.Path(__file__).resolve().parents[3]
        / "src"
        / "temporal"
        / "application"
        / "snapshot_writer.py"
    )
    assert not re.search(r"\.commit\s*\(", path.read_text(encoding="utf-8"))
