"""
Tests for portfolio R/A/G rollup (TASK-V3-021-03, ADR-021).

RED phase: written before implementation.
Scope: RagStatus enum, ProjectRollupEntry, PortfolioRollup, RollupEngine.compute().
Invariant: rollup derived from snapshot history only; no writes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_TENANT = uuid.uuid4()
_T0 = datetime(2026, 8, 11, 8, 0, 0, tzinfo=UTC)


def _snap(
    project_id: uuid.UUID,
    *,
    offset_hours: int = 0,
    overall: float = 0.8,
    open_action_items: int = 0,
) -> ProjectSnapshot:
    ts = _T0 + timedelta(hours=offset_hours)
    return ProjectSnapshot(
        snapshot_id=uuid.uuid4(),
        project_id=project_id,
        tenant_id=_TENANT,
        captured_at=ts,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        health_vector={"overall": overall},
        coherence_subscore=overall,
        counts={"open_action_items": open_action_items, "overdue_reviews": 0},
        totals={},
        created_at=ts,
    )


# ---------------------------------------------------------------------------
# RagStatus
# ---------------------------------------------------------------------------


class TestRagStatus:
    def test_rag_values_exist(self) -> None:
        from src.briefing.domain.rollup import RagStatus

        assert RagStatus.RED
        assert RagStatus.AMBER
        assert RagStatus.GREEN

    def test_rag_is_string_enum(self) -> None:
        from src.briefing.domain.rollup import RagStatus

        assert str(RagStatus.GREEN) in ("green", "GREEN", RagStatus.GREEN.value)


# ---------------------------------------------------------------------------
# ProjectRollupEntry
# ---------------------------------------------------------------------------


class TestProjectRollupEntry:
    def test_fields_accessible(self) -> None:
        from src.briefing.domain.rollup import ProjectRollupEntry, RagStatus

        entry = ProjectRollupEntry(
            project_id=uuid.uuid4(),
            rag_status=RagStatus.GREEN,
            overall_health=0.85,
            open_action_items=2,
            snapshot_count=3,
            latest_snapshot_at=_T0,
        )
        assert entry.rag_status == RagStatus.GREEN
        assert entry.overall_health == pytest.approx(0.85)

    def test_is_immutable(self) -> None:
        from src.briefing.domain.rollup import ProjectRollupEntry, RagStatus

        entry = ProjectRollupEntry(
            project_id=uuid.uuid4(),
            rag_status=RagStatus.AMBER,
            overall_health=0.5,
            open_action_items=0,
            snapshot_count=1,
            latest_snapshot_at=_T0,
        )
        with pytest.raises(Exception):
            entry.rag_status = RagStatus.RED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PortfolioRollup
# ---------------------------------------------------------------------------


class TestPortfolioRollup:
    def test_fields_accessible(self) -> None:
        from src.briefing.domain.rollup import PortfolioRollup, ProjectRollupEntry, RagStatus

        entries = (
            ProjectRollupEntry(
                project_id=uuid.uuid4(),
                rag_status=RagStatus.GREEN,
                overall_health=0.9,
                open_action_items=1,
                snapshot_count=2,
                latest_snapshot_at=_T0,
            ),
        )
        rollup = PortfolioRollup(
            tenant_id=_TENANT,
            generated_at=_T0,
            entries=entries,
        )
        assert rollup.tenant_id == _TENANT
        assert len(rollup.entries) == 1

    def test_counts_by_rag(self) -> None:
        from src.briefing.domain.rollup import PortfolioRollup, ProjectRollupEntry, RagStatus

        entries = (
            ProjectRollupEntry(
                project_id=uuid.uuid4(),
                rag_status=RagStatus.RED,
                overall_health=0.2,
                open_action_items=5,
                snapshot_count=1,
                latest_snapshot_at=_T0,
            ),
            ProjectRollupEntry(
                project_id=uuid.uuid4(),
                rag_status=RagStatus.GREEN,
                overall_health=0.9,
                open_action_items=0,
                snapshot_count=1,
                latest_snapshot_at=_T0,
            ),
            ProjectRollupEntry(
                project_id=uuid.uuid4(),
                rag_status=RagStatus.GREEN,
                overall_health=0.8,
                open_action_items=1,
                snapshot_count=1,
                latest_snapshot_at=_T0,
            ),
        )
        rollup = PortfolioRollup(tenant_id=_TENANT, generated_at=_T0, entries=entries)
        counts = rollup.counts_by_rag
        assert counts[RagStatus.RED] == 1
        assert counts[RagStatus.GREEN] == 2
        assert counts.get(RagStatus.AMBER, 0) == 0


# ---------------------------------------------------------------------------
# RollupEngine.compute()
# ---------------------------------------------------------------------------


class TestRollupEngine:
    def test_empty_snapshot_groups_returns_empty_rollup(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine

        rollup = RollupEngine.compute({})
        assert rollup.entries == ()

    def test_single_project_green(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, overall=0.85)]}
        rollup = RollupEngine.compute(snapshots)
        assert len(rollup.entries) == 1
        assert rollup.entries[0].rag_status == RagStatus.GREEN

    def test_single_project_red(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, overall=0.3)]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].rag_status == RagStatus.RED

    def test_single_project_amber(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, overall=0.55)]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].rag_status == RagStatus.AMBER

    def test_uses_latest_snapshot_health(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        s0 = _snap(pid, offset_hours=0, overall=0.2)
        s1 = _snap(pid, offset_hours=24, overall=0.9)
        snapshots = {pid: [s0, s1]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].rag_status == RagStatus.GREEN

    def test_action_items_from_latest_snapshot(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine

        pid = uuid.uuid4()
        s0 = _snap(pid, offset_hours=0, open_action_items=2)
        s1 = _snap(pid, offset_hours=24, open_action_items=9)
        snapshots = {pid: [s0, s1]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].open_action_items == 9

    def test_snapshot_count_reflects_all_snapshots(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, offset_hours=i) for i in range(5)]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].snapshot_count == 5

    def test_multiple_projects_all_included(self) -> None:
        from src.briefing.application.rollup_engine import RollupEngine

        pids = [uuid.uuid4() for _ in range(3)]
        snapshots = {pid: [_snap(pid)] for pid in pids}
        rollup = RollupEngine.compute(snapshots)
        assert len(rollup.entries) == 3

    def test_rag_thresholds_boundary_green(self) -> None:
        """overall >= 0.7 → GREEN."""
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, overall=0.7)]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].rag_status == RagStatus.GREEN

    def test_rag_thresholds_boundary_amber(self) -> None:
        """0.4 <= overall < 0.7 → AMBER."""
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, overall=0.4)]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].rag_status == RagStatus.AMBER

    def test_rag_thresholds_boundary_red(self) -> None:
        """overall < 0.4 → RED."""
        from src.briefing.application.rollup_engine import RollupEngine
        from src.briefing.domain.rollup import RagStatus

        pid = uuid.uuid4()
        snapshots = {pid: [_snap(pid, overall=0.39)]}
        rollup = RollupEngine.compute(snapshots)
        assert rollup.entries[0].rag_status == RagStatus.RED
