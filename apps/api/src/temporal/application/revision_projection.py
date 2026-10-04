"""Projected Coherence for one revision, through the #714 machinery (PR-C2).

No second engine: the projection is ``project_pending_coherence`` (#714) fed
with exactly the PROPOSED candidate bound to this document revision, over the
trusted artifact set, evaluated by the canonical evaluator the caller passes
(``evaluate_artifact_set`` in production). Nothing here writes: the trusted
Coherence stays the dashboard's canonical value, and approval recomputes
trusted state through the normal pipeline.

The result is always PROJECTED (hypothetical). Its confidence is capped by the
temporal change it rests on, and an unverified or review-required temporal
input marks it ``provisional_unverified_temporal_identity``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.coherence.application.trusted_projection import (
    ProjectionStatus,
    project_pending_coherence,
)
from src.temporal.application.change_qualification import ChangeQualification
from src.temporal.domain.impact import EpistemicBasis

if TYPE_CHECKING:
    from src.analysis.adapters.persistence.document_artifact_repository import PendingCandidate
    from src.analysis.domain.contracts import DocumentArtifact

Qualification = Literal["provisional", "provisional_unverified_temporal_identity"]


class ProjectionCandidate(BaseModel):
    """The exact #714 candidate envelope the projection substituted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: UUID
    artifact_version: int
    artifact_hash: str


class RevisionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    basis: EpistemicBasis = EpistemicBasis.PROJECTED
    status: Literal["none", "provisional", "unavailable"]
    source_revision_id: UUID
    # Canonical evaluator over the trusted artifacts only (the projection baseline).
    trusted_score: float | None = None
    projected_score: float | None = None
    projected_delta: float | None = None
    score_version: str | None = None
    candidate: ProjectionCandidate | None = None
    qualification: Qualification | None = None
    confidence: float | None = None
    reason: str | None = None

    @classmethod
    def none(cls, revision_id: UUID, reason: str) -> RevisionProjection:
        return cls(status="none", source_revision_id=revision_id, reason=reason)


def _matches(candidate: PendingCandidate, document_id: UUID, revision_id: UUID) -> bool:
    artifact = candidate.artifact
    return (
        artifact is not None
        and artifact.document_id == str(document_id)
        and artifact.document_revision_id == str(revision_id)
    )


async def project_revision_coherence(
    *,
    document_id: UUID,
    revision_id: UUID,
    list_pending: Callable[[], Awaitable[Sequence[PendingCandidate]]],
    list_trusted: Callable[[], Awaitable[Sequence[DocumentArtifact]]],
    evaluate: Callable[[list[DocumentArtifact]], Awaitable[Any]],
    qualification: ChangeQualification,
) -> RevisionProjection:
    candidates = [c for c in await list_pending() if _matches(c, document_id, revision_id)]
    if not candidates:
        return RevisionProjection.none(
            revision_id, "no pending candidate is bound to this revision"
        )
    # #714 save() keeps at most one actionable PROPOSED version per document.
    candidate = candidates[-1]

    projection = await project_pending_coherence(
        trusted_artifacts=list(await list_trusted()),
        pending=[candidate],
        evaluate=evaluate,
    )
    unverified = not qualification.identity_verified or qualification.effective_state != "ready"
    binding = candidate.binding
    common: dict[str, Any] = {
        "source_revision_id": revision_id,
        "candidate": ProjectionCandidate(
            artifact_id=binding.artifact_id,
            artifact_version=binding.artifact_version,
            artifact_hash=binding.artifact_hash,
        ),
        "qualification": (
            "provisional_unverified_temporal_identity" if unverified else "provisional"
        ),
        "confidence": qualification.effective_confidence,
    }
    if projection.status is not ProjectionStatus.PROVISIONAL:
        return RevisionProjection(status="unavailable", reason=projection.reason, **common)
    return RevisionProjection(
        status="provisional",
        trusted_score=projection.baseline_score,
        projected_score=projection.projected_score,
        projected_delta=projection.projected_delta,
        score_version=projection.projection_score_version,
        **common,
    )


__all__ = ["ProjectionCandidate", "RevisionProjection", "project_revision_coherence"]
