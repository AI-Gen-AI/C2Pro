"""TS-UT-P0C-TEMPORAL-012 - lineage-aware temporal trust seam (PR-C2, case M/L).

A revision may auto-promote only when its lineage is anchored in a revision the
#714 trust machine explicitly TRUSTED, with no untrusted revision in between.
A clean diff from an untrusted parent proves nothing about the trusted state:

    V1 TRUSTED -> V2 (pending | rejected | superseded) -> V3 clean   => review

The anchor is an artifact bound to exactly that revision with trust_state
TRUSTED. Nothing is guessed: an unbound (legacy) artifact, a broken parent
chain or an over-deep chain fails closed. Artifact types no engine compares are
untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.temporal.application.temporal_review import (
    MAX_LINEAGE_DEPTH,
    TemporalReviewDecision,
    decide_temporal_review,
)
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.revision_trust_reader import RevisionTrustEvidence

TENANT = uuid4()
PROJECT = uuid4()
DOCUMENT = uuid4()


def _rev(
    rev_no: int,
    parent: DocumentRevision | None,
    *,
    document_id: UUID = DOCUMENT,
    tenant_id: UUID = TENANT,
) -> DocumentRevision:
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentRevision(
        revision_id=uuid4(),
        document_id=document_id,
        project_id=PROJECT,
        tenant_id=tenant_id,
        rev_no=rev_no,
        parent_revision_id=parent.revision_id if parent else None,
        blob_hash=f"{rev_no:064d}",
        blob_key=f"revisions/{rev_no}",
        valid_from=now,
        created_at=now,
    )


def _chain(length: int) -> list[DocumentRevision]:
    chain: list[DocumentRevision] = []
    for rev_no in range(1, length + 1):
        chain.append(_rev(rev_no, chain[-1] if chain else None))
    return chain


def _clean_comparison(revision: DocumentRevision) -> list[ProjectEvent]:
    """Revision's own events: analysed and compared by the current matcher, all ready."""
    now = datetime(2026, 10, 4, 10, 0, 0)
    base: dict[str, Any] = {"document_id": str(revision.document_id)}
    change = {
        "object_type": "clause",
        "change_type": "modified",
        "needs_review": False,
        "match_basis": "exact_content",
    }
    return [
        ProjectEvent(
            event_id=uuid4(),
            project_id=revision.project_id,
            tenant_id=revision.tenant_id,
            event_type="revision.analyzed",
            payload={**base, "state": "ready"},
            source_revision_id=revision.revision_id,
            occurred_at=now,
            created_at=now,
        ),
        ProjectEvent(
            event_id=uuid4(),
            project_id=revision.project_id,
            tenant_id=revision.tenant_id,
            event_type="revision.changed",
            payload={
                **base,
                "state": "ready",
                "changeset": {"changes": [change]},
                "provenance": {"diff_engine_version": "p0c-structural-l1-v2"},
            },
            source_revision_id=revision.revision_id,
            occurred_at=now.replace(second=1),
            created_at=now,
        ),
    ]


def _trust(
    states: dict[DocumentRevision, set[str]], *, unbound_trusted: bool = False
) -> RevisionTrustEvidence:
    return RevisionTrustEvidence(
        states_by_revision={rev.revision_id: frozenset(s) for rev, s in states.items()},
        unbound_trusted=unbound_trusted,
    )


def _decide(
    revision: DocumentRevision,
    lineage: list[DocumentRevision],
    trust: RevisionTrustEvidence | None,
    artifact_type: str | None = "contract",
) -> TemporalReviewDecision:
    return decide_temporal_review(
        revision=revision,
        document_id=DOCUMENT,
        events=_clean_comparison(revision),
        artifact_type=artifact_type,
        lineage=lineage,
        trust=trust,
    )


# --- M1-M3: an untrusted parent cannot be crossed by a clean child ----------------


@pytest.mark.parametrize(
    ("v2_states", "detail"),
    [
        ({"proposed"}, "ancestor_pending_review"),  # M1
        ({"rejected"}, "ancestor_rejected"),  # M2
        ({"superseded"}, "ancestor_superseded_without_trusted_successor"),  # M3
        (set(), "ancestor_not_trusted"),  # never analysed/persisted
    ],
)
def test_clean_child_of_an_untrusted_revision_requires_review(
    v2_states: set[str], detail: str
) -> None:
    v1, v2, v3 = _chain(3)

    decision = _decide(v3, [v1, v2, v3], _trust({v1: {"trusted"}, v2: v2_states}))

    assert decision.required is True
    assert decision.reason == "untrusted_ancestor_lineage"
    assert decision.detail == detail


def test_rejected_then_superseded_states_still_block() -> None:
    """A revision whose only artifacts were rejected and superseded is not a baseline."""
    v1, v2, v3 = _chain(3)

    decision = _decide(v3, [v1, v2, v3], _trust({v1: {"trusted"}, v2: {"rejected", "superseded"}}))

    assert decision.required is True
    assert decision.detail == "ancestor_rejected"


def test_gap_deeper_than_the_parent_still_blocks() -> None:
    """V1 TRUSTED -> V2 pending -> V3 TRUSTED? no: V3 pending -> V4 clean."""
    v1, v2, v3, v4 = _chain(4)

    decision = _decide(
        v4, [v1, v2, v3, v4], _trust({v1: {"trusted"}, v2: {"proposed"}, v3: {"proposed"}})
    )

    assert decision.required is True
    assert decision.reason == "untrusted_ancestor_lineage"


# --- M4 / M12: an explicitly TRUSTED revision is the new baseline ---------------------


def test_trusted_parent_anchors_the_lineage() -> None:
    v1, v2, v3 = _chain(3)

    decision = _decide(v3, [v1, v2, v3], _trust({v1: {"trusted"}, v2: {"trusted"}}))

    assert decision == TemporalReviewDecision(required=False, reason="temporal_identity_resolved")


def test_new_trusted_baseline_ends_older_history() -> None:
    """V1 TRUSTED -> V2 rejected -> V3 reviewed + TRUSTED -> V4 clean: V2 no longer blocks."""
    v1, v2, v3, v4 = _chain(4)

    decision = _decide(
        v4,
        [v1, v2, v3, v4],
        _trust({v1: {"trusted"}, v2: {"rejected"}, v3: {"superseded", "trusted"}}),
    )

    assert decision.required is False


def test_trusted_parent_does_not_excuse_the_revisions_own_comparison() -> None:
    """The lineage anchor is necessary, not sufficient: the ordinary rule still applies."""
    v1, v2 = _chain(2)
    events = _clean_comparison(v2)
    events[1] = events[1].model_copy(
        update={"payload": {**events[1].payload, "state": "needs_review"}}
    )

    decision = decide_temporal_review(
        revision=v2,
        document_id=DOCUMENT,
        events=events,
        artifact_type="contract",
        lineage=[v1, v2],
        trust=_trust({v1: {"trusted"}}),
    )

    assert decision.required is True
    assert decision.reason == "temporal_changes_need_review"


# --- M5: never guess a legacy binding --------------------------------------------------


def test_unbound_legacy_trusted_artifact_is_not_guessed_as_baseline() -> None:
    v1, v2 = _chain(2)

    decision = _decide(v2, [v1, v2], _trust({}, unbound_trusted=True))

    assert decision.required is True
    assert decision.reason == "untrusted_ancestor_lineage"
    assert decision.detail == "legacy_unbound_baseline"


def test_no_trusted_baseline_anywhere_fails_closed() -> None:
    v1, v2 = _chain(2)

    decision = _decide(v2, [v1, v2], _trust({v1: {"proposed"}}))

    assert decision.required is True
    assert decision.detail == "ancestor_pending_review"


# --- M6: first revision ---------------------------------------------------------------


def test_first_revision_has_no_lineage_to_validate() -> None:
    (v1,) = _chain(1)

    decision = _decide(v1, [v1], _trust({}))

    assert decision == TemporalReviewDecision(required=False, reason="baseline_revision")


# --- M7: artifact types no engine compares --------------------------------------------


def test_non_compared_artifact_type_is_not_gated_by_lineage() -> None:
    v1, v2 = _chain(2)

    decision = decide_temporal_review(
        revision=v2,
        document_id=DOCUMENT,
        events=[],
        artifact_type="schedule",
        lineage=[v1, v2],
        trust=_trust({v1: {"proposed"}}),
    )

    assert decision == TemporalReviewDecision(required=False, reason="no_temporal_assessment")


# --- M8: broken or unbounded lineage --------------------------------------------------


def test_missing_parent_revision_fails_closed() -> None:
    v1, v2, v3 = _chain(3)

    decision = _decide(v3, [v1, v3], _trust({v1: {"trusted"}}))  # v2 absent from the lineage

    assert decision.required is True
    assert decision.detail == "broken_lineage"


def test_cyclic_lineage_fails_closed() -> None:
    v1, v2 = _chain(2)
    looped = v1.model_copy(update={"parent_revision_id": v2.revision_id})
    v3 = _rev(3, v2)

    decision = _decide(v3, [looped, v2, v3], _trust({}))

    assert decision.required is True
    assert decision.detail == "broken_lineage"


def test_lineage_deeper_than_the_bound_fails_closed() -> None:
    chain = _chain(MAX_LINEAGE_DEPTH + 2)
    trust = _trust({chain[0]: {"trusted"}, **{rev: {"proposed"} for rev in chain[1:-1]}})

    decision = _decide(chain[-1], chain, trust)

    assert decision.required is True
    assert decision.detail == "lineage_depth_exceeded"


def test_missing_lineage_evidence_fails_closed() -> None:
    v1, v2 = _chain(2)

    decision = _decide(v2, [], None)

    assert decision.required is True
    assert decision.detail == "trusted_baseline_not_resolvable"


# --- M9 / M10: other tenants' and documents' revisions never anchor --------------------


def test_revision_of_another_document_cannot_anchor_the_lineage() -> None:
    v1, v2 = _chain(2)
    impostor = v1.model_copy(update={"document_id": uuid4()})

    decision = _decide(v2, [impostor, v2], _trust({impostor: {"trusted"}}))

    assert decision.required is True
    assert decision.detail == "broken_lineage"


def test_revision_of_another_tenant_cannot_anchor_the_lineage() -> None:
    v1, v2 = _chain(2)
    impostor = v1.model_copy(update={"tenant_id": uuid4()})

    decision = _decide(v2, [impostor, v2], _trust({impostor: {"trusted"}}))

    assert decision.required is True
    assert decision.detail == "broken_lineage"


# --- M11: retry / resume re-evaluation is deterministic --------------------------------


def test_reevaluation_returns_the_same_decision() -> None:
    v1, v2, v3 = _chain(3)
    lineage, trust = [v1, v2, v3], _trust({v1: {"trusted"}, v2: {"proposed"}})

    assert _decide(v3, lineage, trust) == _decide(v3, list(reversed(lineage)), trust)
