"""Freeze-lock tests for ProjectSnapshot contracts (ADR-015 / TASK-V3-015-04)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def test_project_snapshot_is_frozen() -> None:
    snapshot = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        captured_at=_now_naive(),
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        health_vector={"risk": {"score": 0.8}},
        created_at=_now_naive(),
    )

    with pytest.raises(ValidationError):
        snapshot.coherence_subscore = 0.9


def test_project_snapshot_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        ProjectSnapshot(
            snapshot_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            captured_at=_now_naive(),
            trigger=SnapshotTrigger.SCHEDULED,
            health_vector={},
            created_at=_now_naive(),
            unexpected=True,
        )


def test_snapshot_trigger_values_are_locked() -> None:
    assert {item.value for item in SnapshotTrigger} == {
        "revision_ingested",
        "graph_completed",
        "hitl_correction",
        "scheduled",
        "baseline_changed",
    }


def test_project_snapshot_rejects_unknown_trigger() -> None:
    with pytest.raises(ValidationError):
        ProjectSnapshot(
            snapshot_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            captured_at=_now_naive(),
            trigger="manual",
            health_vector={},
            created_at=_now_naive(),
        )
