"""#714 projected Coherence contract — RED first."""
from datetime import UTC, datetime

from src.coherence.models import DashboardSummary


def _summary(**overrides: object) -> DashboardSummary:
    data: dict[str, object] = {
        "project_id": "project-1",
        "tenant_id": "tenant-1",
        "global_score": 80.0,
        "coherence_score": 80.0,
        "sub_scores": {},
        "weights_used": {},
        "alert_count": 0,
        "document_count": 1,
        "score_version": "coherence-v1",
        "last_updated": datetime.now(UTC),
    }
    data.update(overrides)
    return DashboardSummary(**data)


def test_dashboard_contract_exposes_trusted_and_projected_scores_separately() -> None:
    summary = _summary(
        trusted_score=80.0,
        projected_score=60.0,
        projected_delta=-20.0,
        pending_review_count=2,
        projection_score_version="coherence-v1",
    )

    assert summary.coherence_score == 80.0
    assert summary.trusted_score == 80.0
    assert summary.projected_score == 60.0
    assert summary.projected_delta == -20.0
    assert summary.pending_review_count == 2
    assert summary.projection_score_version == summary.score_version


def test_projection_supports_unknown_trusted_score_without_fabricating_zero() -> None:
    summary = _summary(
        global_score=None,
        coherence_score=None,
        trusted_score=None,
        projected_score=72.0,
        projected_delta=None,
        pending_review_count=1,
        projection_score_version="coherence-v1",
    )

    assert summary.coherence_score is None
    assert summary.trusted_score is None
    assert summary.projected_score == 72.0
    assert summary.projected_delta is None
