"""Does a revision's temporal interpretation require human review? (PR-C2)

The trust seam the canonical #714 gate consumes: a revision whose temporal
identity is unresolved must not auto-promote to TRUSTED. The decision is
revision/artifact scoped (any artifact type) and derived only from that
revision's own temporal events, qualified at read time exactly as users see
them -- so a legacy or unregistered matcher fails closed too.

Fail-closed cases: unknown revision, a revision of another document, a failed
or incomplete comparison, an analysed revision with a parent but no
comparison, and any comparison whose effective state is not ``ready``.
"No temporal assessment exists" and "a temporal assessment is missing" are
different facts. A revision of an artifact type that no registered engine
compares carries none by design: nothing temporal is asserted, so the ordinary
gate is unchanged. A revision of a compared type (or of an unknown type) that
has a parent but no comparison is missing one and fails closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from src.temporal.application.change_qualification import CHANGE_EVENT_TYPES, qualify_event
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.engine_registry import COMPARED_ARTIFACT_TYPES
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository
from src.temporal.ports.project_event_repository import IProjectEventRepository


@dataclass(frozen=True)
class TemporalReviewDecision:
    required: bool
    reason: str


def _latest(
    events: Sequence[ProjectEvent], types: frozenset[str] | set[str]
) -> ProjectEvent | None:
    matching = [event for event in events if event.event_type in types]
    return (
        max(matching, key=lambda event: (event.occurred_at, event.event_id)) if matching else None
    )


def decide_temporal_review(
    *,
    revision: DocumentRevision | None,
    document_id: UUID,
    events: Sequence[ProjectEvent],
    artifact_type: str | None = None,
) -> TemporalReviewDecision:
    if revision is None:
        return TemporalReviewDecision(True, "revision_not_found")
    if revision.document_id != document_id:
        return TemporalReviewDecision(True, "revision_document_mismatch")
    if revision.parent_revision_id is None:
        return TemporalReviewDecision(False, "baseline_revision")

    own = [event for event in events if event.source_revision_id == revision.revision_id]
    outcome = _latest(own, {*CHANGE_EVENT_TYPES, "revision.analysis_failed"})
    if outcome is not None:
        if outcome.event_type == "revision.analysis_failed":
            return TemporalReviewDecision(True, "temporal_comparison_failed")
        qualification = qualify_event(outcome)
        if not qualification.identity_verified:
            return TemporalReviewDecision(True, "temporal_identity_unverified")
        if qualification.effective_state != "ready":
            return TemporalReviewDecision(True, "temporal_changes_need_review")
        return TemporalReviewDecision(False, "temporal_identity_resolved")

    analyzed = _latest(own, {"revision.analyzed"})
    if analyzed is None:
        if artifact_type is not None and artifact_type not in COMPARED_ARTIFACT_TYPES:
            return TemporalReviewDecision(False, "no_temporal_assessment")
        # A compared (or unidentifiable) artifact type with a parent must have one.
        return TemporalReviewDecision(True, "temporal_comparison_missing")
    if analyzed.payload.get("state") != "ready":
        return TemporalReviewDecision(True, "temporal_comparison_incomplete")
    # Analysed with a parent but never compared: the comparison is missing.
    return TemporalReviewDecision(True, "temporal_comparison_missing")


async def revision_requires_temporal_review(
    *,
    revisions: IDocumentRevisionRepository,
    events: IProjectEventRepository,
    tenant_id: UUID,
    document_id: UUID,
    revision_id: UUID,
    artifact_type: str | None,
) -> TemporalReviewDecision:
    revision = await revisions.get_by_id(revision_id, tenant_id)
    revision_events = await events.list_for_revision(tenant_id=tenant_id, revision_id=revision_id)
    return decide_temporal_review(
        revision=revision,
        document_id=document_id,
        events=revision_events,
        artifact_type=artifact_type,
    )


__all__ = ["TemporalReviewDecision", "decide_temporal_review", "revision_requires_temporal_review"]
