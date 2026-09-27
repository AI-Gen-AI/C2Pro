"""Trusted vs projected Coherence Score (#714).

The trusted score is the canonical dashboard score: only approved/trusted
analysis ever feeds it. The projected score answers "what would the
canonical score be if every pending proposal were accepted unchanged?".

It is NOT recomputed ad hoc. Each pending candidate carries the canonical
engine's own output for its run (N8 ``evaluate_coherence_async`` score and
``score_version``). The dashboard's canonical selection rule is "latest
completed analysis wins", so accepting the pending proposals makes the
latest pending candidate's engine score the canonical one -- that is the
projection. Approving later recomputes the trusted score through the normal
pipeline (N17); the projection is never copied into trusted state.

Guards:
* nothing pending -> no projection;
* never mix score versions (trusted vs candidate) -> unavailable;
* a candidate whose engine produced no score stays null, never 0.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.adapters.persistence.document_artifact_repository import (
        PendingCandidate,
    )


class ProjectionStatus(StrEnum):
    NONE = "none"  # nothing pending review
    PROVISIONAL = "provisional"  # projected_score is a provisional scenario
    UNAVAILABLE = "unavailable"  # pending exists but cannot be projected honestly


@dataclass(frozen=True)
class CoherenceProjection:
    trusted_score: float | None
    projected_score: float | None
    projected_delta: float | None
    pending_review_count: int
    projection_score_version: str | None
    status: ProjectionStatus
    reason: str | None = None


def project_pending_coherence(
    *,
    trusted_score: float | None,
    trusted_score_version: str | None,
    pending: Sequence[PendingCandidate],
) -> CoherenceProjection:
    count = len(pending)

    def _unavailable(reason: str) -> CoherenceProjection:
        return CoherenceProjection(
            trusted_score=trusted_score,
            projected_score=None,
            projected_delta=None,
            pending_review_count=count,
            projection_score_version=None,
            status=ProjectionStatus.UNAVAILABLE,
            reason=reason,
        )

    if count == 0:
        return CoherenceProjection(
            trusted_score=trusted_score,
            projected_score=None,
            projected_delta=None,
            pending_review_count=0,
            projection_score_version=None,
            status=ProjectionStatus.NONE,
        )

    # Deterministic "latest wins", matching the canonical selection rule;
    # ties broken by version then id so input order never matters.
    latest = max(
        pending,
        key=lambda c: (c.created_at, c.binding.artifact_version, str(c.binding.artifact_id)),
    )
    scoring = latest.scoring
    if scoring is None or scoring.coherence_score is None:
        return _unavailable("pending_without_engine_score")
    if scoring.score_version is None:
        return _unavailable("pending_without_score_version")
    if (
        trusted_score is not None
        and trusted_score_version is not None
        and trusted_score_version != scoring.score_version
    ):
        return _unavailable("score_version_mismatch")

    projected = scoring.coherence_score
    return CoherenceProjection(
        trusted_score=trusted_score,
        projected_score=projected,
        projected_delta=(
            round(projected - trusted_score, 4) if trusted_score is not None else None
        ),
        pending_review_count=count,
        projection_score_version=scoring.score_version,
        status=ProjectionStatus.PROVISIONAL,
    )


__all__ = ["CoherenceProjection", "ProjectionStatus", "project_pending_coherence"]
