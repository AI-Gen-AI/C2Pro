"""
TDD proof for TASK-COH-V2-FRONTEND-CATEGORIES: dashboard reads real v2 data
from coherence_v2_shadow when a row exists.

Behavioral contracts:
(a) v2_enabled=True + shadow row exists → categories_v2 from shadow (not adapt_v1)
(b) v2_enabled=True + no shadow row     → categories_v2 via adapt_v1_dashboard fallback
(c) v2_enabled=False                    → categories_v2 remains None

Pure unit tests — no DB, no network, no FastAPI TestClient.

Refers to Suite ID: TASK-COH-V2-FRONTEND-CATEGORIES.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.coherence.models import DashboardSummary
from src.coherence.router import _maybe_add_v2_dashboard


def _minimal_summary(project_id: UUID) -> DashboardSummary:
    return DashboardSummary(
        project_id=str(project_id),
        tenant_id=str(uuid4()),
        global_score=90.0,
        coherence_score=90.0,
        sub_scores={"BUDGET": 85.0, "TIME": 95.0},
        weights_used={"BUDGET": 0.3, "TIME": 0.3},
        alert_count=0,
        document_count=2,
        last_updated=datetime(2026, 8, 7, 15, 0, 0, tzinfo=UTC),
        categories_v2=None,
    )


def _mock_shadow_row(project_id: UUID) -> MagicMock:
    """Minimal shadow ORM row that matches CoherenceV2ShadowORM columns."""
    row = MagicMock()
    row.id = uuid4()
    row.project_id = project_id
    row.coherence_score = 100.0
    row.completeness_score = 0.5
    row.technical_reliability_index = 0.9
    row.active_weight = 0.6
    row.status = "partial"
    row.score_reason = None
    row.created_at = datetime(2026, 8, 7, 15, 25, 49, tzinfo=UTC)
    row.categories_v2 = [
        {
            "category": "BUDGET",
            "status": "scored",
            "coherence_score": 88.0,
            "evidence_coverage": 0.8,
            "technical_reliability": 0.9,
            "evidence_freshness": 1.0,
            "evidence_count": 3,
        },
        {
            "category": "TIME",
            "status": "insufficient_evidence",
            "coherence_score": None,
            "evidence_coverage": 0.0,
            "technical_reliability": 0.0,
            "evidence_freshness": 0.0,
            "evidence_count": 0,
        },
    ]
    return row


def _make_db(*, shadow_row: MagicMock | None) -> AsyncMock:
    """Return an AsyncMock DB session that returns shadow_row on execute+scalar_one_or_none."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = shadow_row

    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_shadow_row_served_when_v2_enabled() -> None:
    """(a) When v2 flag on and shadow row exists, categories_v2 is built from shadow data."""
    project_id = uuid4()
    summary = _minimal_summary(project_id)
    db = _make_db(shadow_row=_mock_shadow_row(project_id))

    result = await _maybe_add_v2_dashboard(
        summary,
        project_id,
        summary.last_updated,
        v2_enabled=True,
        db=db,
    )

    assert result.categories_v2 is not None
    assert result.categories_v2.version == "coherence-v2"
    assert len(result.categories_v2.categories) == 2
    # Real shadow data → first category is BUDGET scored at 88.0
    budget_cat = next(c for c in result.categories_v2.categories if c.category == "BUDGET")
    assert budget_cat.coherence_score == 88.0
    assert budget_cat.evidence_coverage == 0.8
    # Global comes from shadow row columns
    assert result.categories_v2.global_.coherence_score == 100.0
    assert result.categories_v2.global_.completeness_score == 0.5
    assert result.categories_v2.global_.status == "partial"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_adapt_v1_not_called_when_shadow_exists() -> None:
    """(a) adapt_v1_dashboard is NOT called when a real shadow row is available."""
    project_id = uuid4()
    summary = _minimal_summary(project_id)
    db = _make_db(shadow_row=_mock_shadow_row(project_id))

    with patch("src.coherence.adapters.v1_to_v2.adapt_v1_dashboard") as mock_adapt:
        await _maybe_add_v2_dashboard(
            summary, project_id, summary.last_updated, v2_enabled=True, db=db
        )

    mock_adapt.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_b_falls_back_to_adapt_v1_when_no_shadow_row() -> None:
    """(b) When v2 flag on but no shadow row, adapt_v1_dashboard provides categories_v2."""
    from src.coherence.application.dtos.coherence_v2_dtos import CoherenceV2Payload

    project_id = uuid4()
    summary = _minimal_summary(project_id)
    db = _make_db(shadow_row=None)

    fake_v2 = MagicMock(spec=CoherenceV2Payload)
    with patch("src.coherence.adapters.v1_to_v2.adapt_v1_dashboard", return_value=fake_v2) as mock_adapt:
        result = await _maybe_add_v2_dashboard(
            summary, project_id, summary.last_updated, v2_enabled=True, db=db
        )

    mock_adapt.assert_called_once()
    assert result.categories_v2 is fake_v2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_c_v2_disabled_leaves_categories_v2_none() -> None:
    """(c) When v2 flag off, categories_v2 stays None and DB is not queried."""
    project_id = uuid4()
    summary = _minimal_summary(project_id)
    db = _make_db(shadow_row=None)

    result = await _maybe_add_v2_dashboard(
        summary, project_id, summary.last_updated, v2_enabled=False, db=db
    )

    assert result.categories_v2 is None
    db.execute.assert_not_called()
