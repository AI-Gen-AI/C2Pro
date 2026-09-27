"""#714 trusted vs projected Coherence contract -- pure projection rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.analysis.domain.trust import CandidateBinding, CandidateScoring
from src.coherence.application.trusted_projection import (
    ProjectionStatus,
    project_pending_coherence,
)

T0 = datetime(2026, 9, 27, 12, 0, 0)


def _candidate(score: float | None, version: str | None = "coherence-v1", *, at: int = 0):
    from src.analysis.adapters.persistence.document_artifact_repository import (
        PendingCandidate,
    )

    return PendingCandidate(
        binding=CandidateBinding(uuid4(), uuid4(), 1, "a" * 64),
        project_id=uuid4(),
        scoring=CandidateScoring(coherence_score=score, score_version=version),
        created_at=T0 + timedelta(minutes=at),
    )


def test_no_projection_when_nothing_is_pending() -> None:
    p = project_pending_coherence(trusted_score=80.0, trusted_score_version="coherence-v1", pending=[])
    assert p.status is ProjectionStatus.NONE
    assert (p.projected_score, p.projected_delta, p.pending_review_count) == (None, None, 0)
    assert p.trusted_score == 80.0


def test_trusted_score_ignores_pending_and_projected_uses_it() -> None:
    p = project_pending_coherence(
        trusted_score=80.0, trusted_score_version="coherence-v1", pending=[_candidate(60.0)]
    )
    assert p.trusted_score == 80.0
    assert p.projected_score == 60.0
    assert p.projected_delta == -20.0
    assert p.pending_review_count == 1
    assert p.status is ProjectionStatus.PROVISIONAL
    assert p.projection_score_version == "coherence-v1"


def test_reject_removes_candidate_so_projection_returns_to_trusted() -> None:
    # Rejected/superseded candidates are not PROPOSED, so they are simply not
    # in `pending` -- the projection disappears with them.
    before = project_pending_coherence(
        trusted_score=80.0, trusted_score_version="coherence-v1", pending=[_candidate(60.0)]
    )
    after = project_pending_coherence(
        trusted_score=80.0, trusted_score_version="coherence-v1", pending=[]
    )
    assert before.projected_score == 60.0
    assert after.projected_score is None and after.status is ProjectionStatus.NONE


def test_multiple_pending_proposals_fail_honest_not_order_dependent() -> None:
    """Latest-wins over several independent reviews depends on future approval
    order, so no single projected number is honest (#714 coordinator P1)."""
    older, newer = _candidate(70.0, at=0), _candidate(50.0, at=5)
    for pending in ([newer, older], [older, newer]):
        p = project_pending_coherence(
            trusted_score=80.0, trusted_score_version="coherence-v1", pending=pending
        )
        assert p.status is ProjectionStatus.UNAVAILABLE
        assert p.reason == "multiple_pending_order_dependent"
        assert (p.projected_score, p.projected_delta) == (None, None)
        assert p.pending_review_count == 2
        assert p.trusted_score == 80.0


def test_projection_never_mixes_score_versions() -> None:
    p = project_pending_coherence(
        trusted_score=80.0,
        trusted_score_version="coherence-v1",
        pending=[_candidate(60.0, "coherence-v2")],
    )
    assert p.projected_score is None
    assert p.status is ProjectionStatus.UNAVAILABLE
    assert p.reason == "score_version_mismatch"
    assert p.pending_review_count == 1


def test_first_analysis_trusted_null_projected_present() -> None:
    p = project_pending_coherence(
        trusted_score=None, trusted_score_version=None, pending=[_candidate(72.0)]
    )
    assert p.trusted_score is None
    assert p.projected_score == 72.0
    assert p.projected_delta is None, "no delta against an absent trusted score"
    assert p.status is ProjectionStatus.PROVISIONAL


def test_pending_without_engine_score_stays_null_not_zero() -> None:
    p = project_pending_coherence(
        trusted_score=80.0, trusted_score_version="coherence-v1", pending=[_candidate(None)]
    )
    assert p.projected_score is None
    assert p.status is ProjectionStatus.UNAVAILABLE
    assert p.pending_review_count == 1
