"""
Tests for snapshot projection layer (TASK-V3-021-01, ADR-021).

RED phase: written before implementation.
Scope: MorningBriefingProjection model, ProjectionEngine.project() pure function,
       SnapshotProjectionUseCase.
Invariant: projection derives from snapshots only — no writes, no new source of truth.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from src.briefing.application.projection_engine import ProjectionEngine
from src.briefing.domain.projection import HealthDelta, MorningBriefingProjection
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PROJECT = uuid.uuid4()
_TENANT = uuid.uuid4()
_T0 = datetime(2026, 8, 11, 8, 0, 0, tzinfo=UTC)


def _snap(
    *,
    offset_hours: int = 0,
    health_vector: dict | None = None,
    counts: dict | None = None,
    trigger: SnapshotTrigger = SnapshotTrigger.GRAPH_COMPLETED,
    project_id: UUID | None = None,
) -> ProjectSnapshot:
    ts = _T0 + timedelta(hours=offset_hours)
    return ProjectSnapshot(
        snapshot_id=uuid.uuid4(),
        project_id=project_id or _PROJECT,
        tenant_id=_TENANT,
        captured_at=ts,
        trigger=trigger,
        health_vector=health_vector or {"overall": 0.8},
        coherence_subscore=0.75,
        counts=counts or {"open_action_items": 0, "overdue_reviews": 0},
        totals={},
        created_at=ts,
    )


# ---------------------------------------------------------------------------
# HealthDelta model
# ---------------------------------------------------------------------------


class TestHealthDelta:
    def test_delta_computed(self) -> None:
        d = HealthDelta(dimension="cost", previous=0.6, current=0.8)
        assert d.delta == pytest.approx(0.2, abs=1e-6)

    def test_negative_delta(self) -> None:
        d = HealthDelta(dimension="risk", previous=0.9, current=0.7)
        assert d.delta == pytest.approx(-0.2, abs=1e-6)

    def test_zero_delta(self) -> None:
        d = HealthDelta(dimension="cost", previous=0.5, current=0.5)
        assert d.delta == pytest.approx(0.0, abs=1e-6)

    def test_is_immutable(self) -> None:
        d = HealthDelta(dimension="x", previous=0.5, current=0.6)
        with pytest.raises(Exception):
            d.dimension = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MorningBriefingProjection model
# ---------------------------------------------------------------------------


class TestMorningBriefingProjection:
    def test_fields_accessible(self) -> None:
        s = _snap()
        proj = MorningBriefingProjection(
            project_id=_PROJECT,
            snapshot_from_id=None,
            snapshot_to_id=s.snapshot_id,
            period_start=_T0,
            period_end=_T0,
            generated_at=_T0,
            health_deltas=(),
            new_action_item_count=0,
            overdue_review_count=0,
            trigger_events=(),
            evidence_refs=(str(s.snapshot_id),),
        )
        assert proj.project_id == _PROJECT
        assert proj.new_action_item_count == 0

    def test_is_immutable(self) -> None:
        s = _snap()
        proj = MorningBriefingProjection(
            project_id=_PROJECT,
            snapshot_from_id=None,
            snapshot_to_id=s.snapshot_id,
            period_start=_T0,
            period_end=_T0,
            generated_at=_T0,
            health_deltas=(),
            new_action_item_count=0,
            overdue_review_count=0,
            trigger_events=(),
            evidence_refs=(),
        )
        with pytest.raises(Exception):
            proj.new_action_item_count = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ProjectionEngine.project() pure function
# ---------------------------------------------------------------------------


class TestProjectionEngine:
    def test_raises_on_empty_snapshots(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            ProjectionEngine.project([])

    def test_single_snapshot_no_deltas(self) -> None:
        s = _snap(health_vector={"overall": 0.8})
        proj = ProjectionEngine.project([s])
        assert proj.snapshot_from_id is None
        assert proj.snapshot_to_id == s.snapshot_id
        assert proj.health_deltas == ()

    def test_two_snapshots_computes_health_delta(self) -> None:
        s0 = _snap(offset_hours=0, health_vector={"overall": 0.6, "cost": 0.7})
        s1 = _snap(offset_hours=24, health_vector={"overall": 0.8, "cost": 0.6})
        proj = ProjectionEngine.project([s0, s1])
        assert proj.snapshot_from_id == s0.snapshot_id
        assert proj.snapshot_to_id == s1.snapshot_id
        deltas_by_dim = {d.dimension: d for d in proj.health_deltas}
        assert deltas_by_dim["overall"].delta == pytest.approx(0.2, abs=1e-6)
        assert deltas_by_dim["cost"].delta == pytest.approx(-0.1, abs=1e-6)

    def test_action_item_delta_computed(self) -> None:
        s0 = _snap(counts={"open_action_items": 3, "overdue_reviews": 0})
        s1 = _snap(counts={"open_action_items": 7, "overdue_reviews": 2}, offset_hours=24)
        proj = ProjectionEngine.project([s0, s1])
        assert proj.new_action_item_count == 4
        assert proj.overdue_review_count == 2

    def test_overdue_reviews_taken_from_latest(self) -> None:
        s0 = _snap(counts={"open_action_items": 0, "overdue_reviews": 1})
        s1 = _snap(counts={"open_action_items": 0, "overdue_reviews": 5}, offset_hours=24)
        proj = ProjectionEngine.project([s0, s1])
        assert proj.overdue_review_count == 5

    def test_trigger_events_recorded(self) -> None:
        s0 = _snap(trigger=SnapshotTrigger.GRAPH_COMPLETED)
        s1 = _snap(trigger=SnapshotTrigger.HITL_CORRECTION, offset_hours=12)
        s2 = _snap(trigger=SnapshotTrigger.REVISION_INGESTED, offset_hours=24)
        proj = ProjectionEngine.project([s0, s1, s2])
        assert any("hitl_correction" in e.lower() for e in proj.trigger_events)

    def test_evidence_refs_include_snapshot_ids(self) -> None:
        s0 = _snap()
        s1 = _snap(offset_hours=24)
        proj = ProjectionEngine.project([s0, s1])
        assert str(s0.snapshot_id) in proj.evidence_refs
        assert str(s1.snapshot_id) in proj.evidence_refs

    def test_period_start_and_end_from_snapshots(self) -> None:
        s0 = _snap(offset_hours=0)
        s1 = _snap(offset_hours=24)
        proj = ProjectionEngine.project([s0, s1])
        assert proj.period_start == s0.captured_at
        assert proj.period_end == s1.captured_at

    def test_project_id_propagated(self) -> None:
        pid = uuid.uuid4()
        s = _snap(project_id=pid)
        proj = ProjectionEngine.project([s])
        assert proj.project_id == pid

    def test_snapshots_processed_in_chronological_order(self) -> None:
        """Even if supplied out of order, first/last are by captured_at."""
        s0 = _snap(offset_hours=0, health_vector={"overall": 0.5})
        s1 = _snap(offset_hours=24, health_vector={"overall": 0.9})
        proj_forward = ProjectionEngine.project([s0, s1])
        proj_backward = ProjectionEngine.project([s1, s0])
        assert proj_forward.health_deltas == proj_backward.health_deltas

    def test_new_health_keys_in_latest_snapshot_included(self) -> None:
        """Key added in s1 but absent in s0 → previous=0.0."""
        s0 = _snap(health_vector={"overall": 0.7})
        s1 = _snap(health_vector={"overall": 0.7, "legal": 0.5}, offset_hours=24)
        proj = ProjectionEngine.project([s0, s1])
        deltas_by_dim = {d.dimension: d for d in proj.health_deltas}
        assert "legal" in deltas_by_dim
        assert deltas_by_dim["legal"].previous == 0.0

    def test_missing_health_keys_in_latest_snapshot_included(self) -> None:
        """Key dropped from s1 → current=0.0."""
        s0 = _snap(health_vector={"overall": 0.7, "risk": 0.8})
        s1 = _snap(health_vector={"overall": 0.7}, offset_hours=24)
        proj = ProjectionEngine.project([s0, s1])
        deltas_by_dim = {d.dimension: d for d in proj.health_deltas}
        assert "risk" in deltas_by_dim
        assert deltas_by_dim["risk"].current == 0.0


# ---------------------------------------------------------------------------
# SnapshotProjectionUseCase
# ---------------------------------------------------------------------------


class TestSnapshotProjectionUseCase:
    @pytest.mark.asyncio
    async def test_fetches_snapshots_and_projects(self) -> None:
        from unittest.mock import AsyncMock

        from src.briefing.application.snapshot_projection_use_case import (
            BriefingRequest,
            SnapshotProjectionUseCase,
        )

        s0 = _snap(offset_hours=0, counts={"open_action_items": 2, "overdue_reviews": 0})
        s1 = _snap(offset_hours=24, counts={"open_action_items": 5, "overdue_reviews": 1})

        repo = AsyncMock()
        repo.list_since.return_value = [s0, s1]

        uc = SnapshotProjectionUseCase(snapshot_repository=repo)
        since = _T0 - timedelta(hours=1)
        request = BriefingRequest(
            project_id=_PROJECT,
            tenant_id=_TENANT,
            since=since,
        )
        proj = await uc.execute(request)

        assert proj.project_id == _PROJECT
        assert proj.new_action_item_count == 3
        repo.list_since.assert_awaited_once_with(_PROJECT, _TENANT, since)

    @pytest.mark.asyncio
    async def test_raises_when_no_snapshots_available(self) -> None:
        from unittest.mock import AsyncMock

        from src.briefing.application.snapshot_projection_use_case import (
            BriefingRequest,
            SnapshotProjectionUseCase,
        )

        repo = AsyncMock()
        repo.list_since.return_value = []

        uc = SnapshotProjectionUseCase(snapshot_repository=repo)
        request = BriefingRequest(project_id=_PROJECT, tenant_id=_TENANT, since=_T0)
        with pytest.raises(ValueError):
            await uc.execute(request)
