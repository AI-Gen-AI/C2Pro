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

Lineage (case M/L): a clean comparison against an UNTRUSTED parent proves
nothing about the trusted state. For a compared (or unidentifiable) artifact
type, a revision may pass only when its parent chain reaches -- with nothing
in between -- a revision the #714 trust machine explicitly TRUSTED: an
artifact bound to exactly that revision with trust_state ``trusted``. TRUSTED
rows are never demoted, so the nearest such revision is the current anchor and
older history behind it no longer matters. A pending, rejected, superseded or
never-trusted revision in between, an unbound (legacy) artifact standing in for
a baseline, a broken or cyclic chain, or a chain deeper than
``MAX_LINEAGE_DEPTH`` all fail closed as ``untrusted_ancestor_lineage``; the
specific cause is carried in ``detail``. The first revision has no lineage.
A revision that is itself already TRUSTED (re-analysed) anchors at itself, but
only after its own new comparison is clean: earlier trust never masks a new
unresolved comparison.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from src.analysis.domain.trust import TrustState
from src.temporal.application.change_qualification import CHANGE_EVENT_TYPES, qualify_event
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.engine_registry import COMPARED_ARTIFACT_TYPES
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository
from src.temporal.ports.project_event_repository import IProjectEventRepository
from src.temporal.ports.revision_trust_reader import IRevisionTrustReader, RevisionTrustEvidence

# Defensive bound on the parent walk (revision chains are short in practice).
MAX_LINEAGE_DEPTH = 256
UNTRUSTED_ANCESTOR_LINEAGE = "untrusted_ancestor_lineage"


@dataclass(frozen=True)
class TemporalReviewDecision:
    required: bool
    reason: str
    # Internal specific cause (e.g. ``ancestor_rejected``); the public reason stays small.
    detail: str | None = None


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
    lineage: Sequence[DocumentRevision] | None = None,
    trust: RevisionTrustEvidence | None = None,
) -> TemporalReviewDecision:
    own_decision = _own_comparison_decision(
        revision=revision, document_id=document_id, events=events, artifact_type=artifact_type
    )
    if own_decision.required or revision is None or revision.parent_revision_id is None:
        return own_decision
    if artifact_type is not None and artifact_type not in COMPARED_ARTIFACT_TYPES:
        # No engine compares this type: lineage asserts nothing, the ordinary gate applies.
        return own_decision
    return _lineage_decision(revision, lineage, trust) or own_decision


def _untrusted(detail: str) -> TemporalReviewDecision:
    return TemporalReviewDecision(True, UNTRUSTED_ANCESTOR_LINEAGE, detail)


def _gap_detail(states: frozenset[str]) -> str:
    if TrustState.PROPOSED.value in states:
        return "ancestor_pending_review"
    if TrustState.REJECTED.value in states:
        return "ancestor_rejected"
    if TrustState.SUPERSEDED.value in states:
        return "ancestor_superseded_without_trusted_successor"
    return "ancestor_not_trusted"


def _lineage_decision(
    revision: DocumentRevision,
    lineage: Sequence[DocumentRevision] | None,
    trust: RevisionTrustEvidence | None,
) -> TemporalReviewDecision | None:
    """None when the parent chain is anchored in an explicitly TRUSTED revision."""
    if lineage is None or trust is None:
        return _untrusted("trusted_baseline_not_resolvable")
    # An explicit #714 approval of THIS revision already made it a trusted baseline:
    # history behind it is not re-litigated. Reached only after its own (new)
    # comparison passed, so earlier trust never masks a new unresolved comparison.
    if TrustState.TRUSTED.value in trust.states_by_revision.get(revision.revision_id, frozenset()):
        return None
    # Only this document's own revisions in this tenant can form its lineage.
    by_id = {
        node.revision_id: node
        for node in lineage
        if node.document_id == revision.document_id and node.tenant_id == revision.tenant_id
    }
    gap: list[frozenset[str]] = []
    seen: set[UUID] = {revision.revision_id}
    current = revision.parent_revision_id
    for _ in range(MAX_LINEAGE_DEPTH):
        if current is None:
            # Walked past the first revision without meeting a bound TRUSTED one.
            if trust.unbound_trusted:
                return _untrusted("legacy_unbound_baseline")
            return _untrusted(_gap_detail(gap[0]) if gap else "trusted_baseline_not_resolvable")
        node = by_id.get(current)
        if node is None or current in seen:
            return _untrusted("broken_lineage")
        seen.add(current)
        states = trust.states_by_revision.get(current, frozenset())
        if TrustState.TRUSTED.value in states:
            return _untrusted(_gap_detail(gap[0])) if gap else None
        gap.append(states)
        current = node.parent_revision_id
    return _untrusted("lineage_depth_exceeded")


def _own_comparison_decision(
    *,
    revision: DocumentRevision | None,
    document_id: UUID,
    events: Sequence[ProjectEvent],
    artifact_type: str | None,
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
    trust: IRevisionTrustReader,
    tenant_id: UUID,
    document_id: UUID,
    revision_id: UUID,
    artifact_type: str | None,
) -> TemporalReviewDecision:
    revision = await revisions.get_by_id(revision_id, tenant_id)
    revision_events = await events.list_for_revision(tenant_id=tenant_id, revision_id=revision_id)
    needs_lineage = (
        revision is not None
        and revision.document_id == document_id
        and revision.parent_revision_id is not None
        and (artifact_type is None or artifact_type in COMPARED_ARTIFACT_TYPES)
    )
    # Two bounded reads: the document's revisions and its artifacts' trust states.
    lineage = await revisions.list_lineage(document_id, tenant_id) if needs_lineage else None
    trust_evidence = (
        await trust.read(tenant_id=tenant_id, document_id=document_id) if needs_lineage else None
    )
    return decide_temporal_review(
        revision=revision,
        document_id=document_id,
        events=revision_events,
        artifact_type=artifact_type,
        lineage=lineage,
        trust=trust_evidence,
    )


__all__ = [
    "MAX_LINEAGE_DEPTH",
    "UNTRUSTED_ANCESTOR_LINEAGE",
    "TemporalReviewDecision",
    "decide_temporal_review",
    "revision_requires_temporal_review",
]
