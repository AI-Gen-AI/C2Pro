"""#714: official reports/exports use the TRUSTED coherence score only."""

from __future__ import annotations

from datetime import UTC, datetime

from src.coherence.models import DashboardSummary
from src.reporting.application.current_state_projection import project_coherence
from src.reporting.application.ports import SourceOk


def _summary(**projection) -> DashboardSummary:
    return DashboardSummary(
        project_id="p",
        tenant_id="t",
        global_score=80.0,
        coherence_score=80.0,
        trusted_score=80.0,
        sub_scores={"LEGAL": 80.0},
        weights_used={"LEGAL": 1.0},
        alert_count=0,
        document_count=1,
        score_version="coherence-v1",
        last_updated=datetime(2026, 9, 27, tzinfo=UTC),
        **projection,
    )


def test_report_uses_trusted_score_even_with_pending_projection() -> None:
    section = project_coherence(
        SourceOk(
            _summary(
                projected_score=60.0,
                projected_delta=-20.0,
                pending_review_count=2,
                projection_score_version="coherence-v1",
                projection_status="provisional",
            )
        )
    )

    assert section.data is not None
    assert section.data.score == 80.0
    dumped = section.data.model_dump()
    assert 60.0 not in dumped.values()
    assert not any("projected" in key for key in dumped)


def test_report_without_trusted_evidence_stays_unavailable_despite_projection() -> None:
    summary = _summary(projected_score=72.0, projection_status="provisional").model_copy(
        update={
            "global_score": None,
            "coherence_score": None,
            "trusted_score": None,
            "score_version": None,
        }
    )
    section = project_coherence(SourceOk(summary))
    assert section.data is None
