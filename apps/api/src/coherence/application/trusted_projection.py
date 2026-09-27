"""Trusted vs projected Coherence Score (#714).

The projection answers: "what would the canonical project Coherence be if
EVERY currently actionable pending proposal were accepted unchanged?"

    baseline  = canonical evaluator(trusted artifact set)
    projected = canonical evaluator(trusted artifact set with each actionable
                                    PROPOSED candidate substituted for its
                                    document)

Both go through ``evaluate_artifact_set`` -- the exact ProjectGraph
evaluation (same aggregation, engine and score_version). Stored per-run
candidate scores are provenance only and never used here; nothing is
"latest wins" and nothing is ad-hoc arithmetic. Approving later recomputes
the trusted state through the normal pipeline; the projection is never
copied into trusted state.

Fail-honest guards (projection unavailable, trusted untouched):
* nothing pending -> no projection (and no evaluation);
* a pending candidate without its exact artifact payload;
* the evaluation failing;
* baseline and projection (or the dashboard's own score) on different
  score versions;
* null stays null, never 0.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.analysis.adapters.graph.project_graph import ArtifactSetEvaluation
    from src.analysis.adapters.persistence.document_artifact_repository import (
        PendingCandidate,
    )
    from src.analysis.domain.contracts import DocumentArtifact

logger = structlog.get_logger()

ArtifactSetEvaluator = Callable[[list["DocumentArtifact"]], Awaitable["ArtifactSetEvaluation"]]


class ProjectionStatus(StrEnum):
    NONE = "none"  # nothing pending review
    PROVISIONAL = "provisional"  # projected_score is a provisional scenario
    UNAVAILABLE = "unavailable"  # pending exists but cannot be projected honestly


@dataclass(frozen=True)
class CoherenceProjection:
    baseline_score: float | None
    projected_score: float | None
    projected_delta: float | None
    pending_review_count: int
    projection_score_version: str | None
    status: ProjectionStatus
    reason: str | None = None


def _scenario(
    trusted: Sequence[DocumentArtifact], pending: Sequence[PendingCandidate]
) -> list[DocumentArtifact]:
    """Trusted set with each pending candidate substituted for its document."""
    by_document = {artifact.document_id: artifact for artifact in trusted}
    for candidate in pending:
        assert candidate.artifact is not None
        by_document[candidate.artifact.document_id] = candidate.artifact
    return [by_document[key] for key in sorted(by_document)]


async def project_pending_coherence(
    *,
    trusted_artifacts: Sequence[DocumentArtifact],
    pending: Sequence[PendingCandidate],
    evaluate: ArtifactSetEvaluator,
    trusted_score_version: str | None = None,
) -> CoherenceProjection:
    count = len(pending)

    def _unavailable(reason: str) -> CoherenceProjection:
        return CoherenceProjection(
            baseline_score=None,
            projected_score=None,
            projected_delta=None,
            pending_review_count=count,
            projection_score_version=None,
            status=ProjectionStatus.UNAVAILABLE,
            reason=reason,
        )

    if count == 0:
        return CoherenceProjection(
            baseline_score=None,
            projected_score=None,
            projected_delta=None,
            pending_review_count=0,
            projection_score_version=None,
            status=ProjectionStatus.NONE,
        )
    if any(candidate.artifact is None for candidate in pending):
        return _unavailable("pending_candidate_payload_missing")

    trusted = sorted(trusted_artifacts, key=lambda a: a.document_id)
    try:
        # First analysis: no trusted artifacts -> no baseline to evaluate.
        baseline = await evaluate(list(trusted)) if trusted else None
        projected = await evaluate(_scenario(trusted, pending))
    except Exception:  # noqa: BLE001 - a projection never breaks the dashboard
        logger.warning("coherence_projection_evaluation_failed", exc_info=True)
        return _unavailable("projection_evaluation_failed")

    version = projected.score_version
    if (baseline is not None and baseline.score_version != version) or (
        trusted_score_version is not None and version is not None and trusted_score_version != version
    ):
        return _unavailable("score_version_mismatch")

    projected_score = projected.summary.overall_score
    if projected_score is None:
        return _unavailable(projected.summary.score_reason or "projection_insufficient_evidence")
    baseline_score = baseline.summary.overall_score if baseline is not None else None
    return CoherenceProjection(
        baseline_score=baseline_score,
        projected_score=projected_score,
        projected_delta=(
            round(projected_score - baseline_score, 4) if baseline_score is not None else None
        ),
        pending_review_count=count,
        projection_score_version=version,
        status=ProjectionStatus.PROVISIONAL,
    )


__all__ = [
    "ArtifactSetEvaluator",
    "CoherenceProjection",
    "ProjectionStatus",
    "project_pending_coherence",
]
