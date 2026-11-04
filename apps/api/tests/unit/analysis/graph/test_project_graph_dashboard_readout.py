"""The existing dashboard reads the newest trustworthy ProjectGraph snapshot."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.coherence.models import DashboardSummary


class FakeDB:
    def __init__(self, record):
        self.record = record

    async def scalar(self, _query):
        return self.record


def existing_dashboard(now):
    return DashboardSummary(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        global_score=80,
        coherence_score=80,
        sub_scores={"LEGAL": 80},
        weights_used={"LEGAL": 1.0},
        alert_count=2,
        document_count=4,
        methodology_version="3.0",
        score_version="coherence-v1",
        last_updated=now - timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_dashboard_prefers_latest_projectgraph_with_honest_unknown():
    from src.coherence.router import _prefer_current_projectgraph_snapshot

    now = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
    snap = SimpleNamespace(
        captured_at=now,
        coherence_subscore=None,
        counts={
            "project_graph": True,
            "score_reason": "insufficient_verified_dimensions",
            "missing_dimensions": ["BUDGET", "TECHNICAL"],
            "category_scores": {"LEGAL": 60, "BUDGET": None},
            "score_version": "coherence-v1",
        },
    )
    initial = existing_dashboard(now)
    result = await _prefer_current_projectgraph_snapshot(
        initial,
        db=FakeDB(snap),
        project_id=uuid4(),
        tenant_id=uuid4(),
        latest_source_at=now - timedelta(minutes=5),
    )
    assert result.coherence_score is None
    assert result.global_score is None
    assert result.trusted_score is None
    assert result.sub_scores["LEGAL"] == 60
    assert result.sub_scores["BUDGET"] is None
    assert result.score_version == "coherence-v1"
    assert result.score_missing_dimensions == ["BUDGET", "TECHNICAL"]
    assert result.score_reason == "insufficient_verified_dimensions"
    # Revalidate exactly as FastAPI will validate the dashboard response.
    assert DashboardSummary.model_validate(result.model_dump()).coherence_score is None


@pytest.mark.asyncio
async def test_older_projectgraph_result_never_overrides_newer_documents():
    from src.coherence.router import _prefer_current_projectgraph_snapshot

    now = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
    old = SimpleNamespace(
        captured_at=now - timedelta(hours=2),
        coherence_subscore=95,
        counts={"project_graph": True, "score_version": "coherence-v1"},
    )
    initial = existing_dashboard(now)
    result = await _prefer_current_projectgraph_snapshot(
        initial,
        db=FakeDB(old),
        project_id=uuid4(),
        tenant_id=uuid4(),
        latest_source_at=now - timedelta(minutes=15),
    )
    assert result is initial
    assert result.coherence_score == 80


@pytest.mark.asyncio
async def test_projectgraph_snapshot_missing_preserves_original_dashboard():
    from src.coherence.router import _prefer_current_projectgraph_snapshot

    now = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
    initial = existing_dashboard(now)
    result = await _prefer_current_projectgraph_snapshot(
        initial,
        db=FakeDB(None),
        project_id=uuid4(),
        tenant_id=uuid4(),
        latest_source_at=None,
    )
    assert result is initial
