"""#758 P1: the canonical resumability identity, as a decision matrix.

Three races -- the generation/reupload window, an approval already in flight
when the review is rebound, and a stale `resume_operations` row -- all reduce
to two comparisons:

1. is the review's lineage still current for its document?
2. is the operation bound to the review's CURRENT lineage?

:func:`~src.core.resume_lineage.decide_resume_lineage` is pure, so the whole
matrix is asserted here without a database, and the integration races then
prove the seams actually consult it.

The cases that must stay ALLOWED matter as much as the refusals: a legacy
review (no lineage recorded) and a document that was never processed under
#711 have nothing to compare against, and refusing them would strand rows
this identity was never meant to govern.
"""

from __future__ import annotations

from uuid import uuid4

from src.core import resume_lineage
from src.core.resume_lineage import ReviewLineage, decide_resume_lineage

A_THREAD = "document:11111111-1111-4111-8111-111111111111:g1:f1:analysis"
B_THREAD = "document:11111111-1111-4111-8111-111111111111:g1:f2:analysis"
LEGACY_THREAD = "document:11111111-1111-4111-8111-111111111111:analysis"


def _lineage(
    *,
    thread_id: str | None = A_THREAD,
    generation: int | None = 1,
    fence: int | None = 1,
    authority_generation: int | None = 1,
    authority_fence: int | None = 1,
) -> ReviewLineage:
    return ReviewLineage(
        review_row_id=uuid4(),
        thread_id=thread_id,
        document_id=uuid4(),
        lineage_generation=generation,
        lineage_fencing_token=fence,
        authority_generation=authority_generation,
        authority_fencing_token=authority_fence,
    )


# ── the happy path, and the legacy paths that must keep working ──────────────


def test_current_lineage_with_a_matching_operation_is_allowed() -> None:
    decision = decide_resume_lineage(
        _lineage(),
        authorized_thread_id=A_THREAD,
        operation_thread_id=A_THREAD,
        operation_phase="FAILED_RETRYABLE",
    )
    assert decision.allowed
    assert not decision.adopt_operation_lineage


def test_a_legacy_review_records_no_lineage_and_is_never_refused_for_currency() -> None:
    """Production still has pending reviews bound before this identity existed.

    They carry no generation and no fence, so there is nothing to compare;
    they keep resuming exactly as they did, and the pre-#758 shared-thread
    refusal in the use case remains their guard.
    """
    lineage = _lineage(
        thread_id=LEGACY_THREAD,
        generation=None,
        fence=None,
        authority_generation=7,
        authority_fence=9,
    )
    assert not lineage.is_fenced
    assert lineage.is_current_for_document
    assert decide_resume_lineage(
        lineage,
        authorized_thread_id=LEGACY_THREAD,
        operation_thread_id=LEGACY_THREAD,
        operation_phase="PENDING",
    ).allowed


def test_a_document_never_processed_under_711_has_nothing_to_compare() -> None:
    lineage = _lineage(authority_generation=None, authority_fence=None)
    assert lineage.is_current_for_document
    assert decide_resume_lineage(
        lineage,
        authorized_thread_id=A_THREAD,
        operation_thread_id=A_THREAD,
        operation_phase="RUNNING",
    ).allowed


# ── P1-1: the generation / reupload window ──────────────────────────────────


def test_a_newer_generation_makes_the_review_lineage_non_current() -> None:
    """The exact invariant: a new revision/reprocess ends resumability at once.

    Nothing about the review row changed -- same thread, same fence -- yet the
    document's grant moved to generation 2. That is the whole window between
    "the new generation is authoritative" and "the replacement attempt reaches
    the HITL gate", and an approval inside it must not resume the old lineage.
    """
    lineage = _lineage(generation=1, fence=1, authority_generation=2, authority_fence=2)
    assert not lineage.is_current_for_document
    decision = decide_resume_lineage(
        lineage,
        authorized_thread_id=A_THREAD,
        operation_thread_id=A_THREAD,
        operation_phase="PENDING",
    )
    assert decision.refusal == resume_lineage.REVIEW_LINEAGE_NOT_CURRENT


def test_a_newer_fence_in_the_same_generation_is_also_non_current() -> None:
    """A takeover after a lease expiry supersedes the lineage too.

    Same generation, new attempt. Defence in depth behind the pre-graph
    claim: if the replacement attempt dies before claiming, the review must
    still not be resumable through the attempt it replaced.
    """
    lineage = _lineage(generation=1, fence=1, authority_generation=1, authority_fence=2)
    assert not lineage.is_current_for_document
    assert (
        decide_resume_lineage(
            lineage,
            authorized_thread_id=A_THREAD,
            operation_thread_id=A_THREAD,
            operation_phase="RUNNING",
        ).refusal
        == resume_lineage.REVIEW_LINEAGE_NOT_CURRENT
    )


# ── P1-2: the approval already in flight ────────────────────────────────────


def test_a_rebind_between_authorization_and_acquisition_fails_closed() -> None:
    """The caller read lineage A; B rebound the review before it acquired.

    Checked BEFORE currency, because this caller is superseded whatever the
    new lineage's own standing is -- it restored a checkpoint from a lineage
    the review no longer names.
    """
    rebound = _lineage(thread_id=B_THREAD, generation=1, fence=2, authority_fence=2)
    assert rebound.is_current_for_document, "B's own lineage is perfectly current"
    assert (
        decide_resume_lineage(
            rebound,
            authorized_thread_id=A_THREAD,
            operation_thread_id=A_THREAD,
            operation_phase="RUNNING",
        ).refusal
        == resume_lineage.REVIEW_LINEAGE_REBOUND
    )


def test_a_missing_review_row_fails_closed() -> None:
    assert (
        decide_resume_lineage(
            None,
            authorized_thread_id=A_THREAD,
            operation_thread_id=A_THREAD,
            operation_phase="PENDING",
        ).refusal
        == resume_lineage.REVIEW_ROW_MISSING
    )


# ── P1-3: an operation left behind on a superseded lineage ──────────────────


def test_a_durable_operation_may_never_be_repointed_at_another_lineage() -> None:
    """N17_DURABLE / GRAPH_COMPLETED are refused, not adopted.

    The analysis, its `analysis.persisted` event and any `graph.completed`
    marker belong to the run that produced them. Re-pointing such an
    operation would let lineage A's business effects finalize against the
    current review and document -- exactly what must be impossible.
    """
    rebound = _lineage(thread_id=B_THREAD, generation=1, fence=2, authority_fence=2)
    for phase in sorted(resume_lineage.PHASES_WITH_DURABLE_EFFECT):
        decision = decide_resume_lineage(
            rebound,
            authorized_thread_id=B_THREAD,
            operation_thread_id=A_THREAD,
            operation_phase=phase,
        )
        assert decision.refusal == resume_lineage.OPERATION_LINEAGE_SUPERSEDED, phase
        assert not decision.adopt_operation_lineage


def test_an_operation_with_no_durable_effect_adopts_the_current_lineage() -> None:
    """Otherwise a rebound review would be permanently unapprovable.

    A PENDING / RUNNING / FAILED_RETRYABLE operation is a lifecycle shell:
    there is exactly one per review row, so refusing it outright would leave
    the human with no way to approve the review the current attempt owns.
    """
    rebound = _lineage(thread_id=B_THREAD, generation=1, fence=2, authority_fence=2)
    for phase in ("PENDING", "RUNNING", "FAILED_RETRYABLE"):
        decision = decide_resume_lineage(
            rebound,
            authorized_thread_id=B_THREAD,
            operation_thread_id=A_THREAD,
            operation_phase=phase,
        )
        assert decision.allowed, phase
        assert decision.adopt_operation_lineage, phase


def test_an_operation_with_no_recorded_lineage_yet_is_not_treated_as_stale() -> None:
    """A freshly upserted operation has whatever thread the insert gave it.

    None means "nothing to compare", not "mismatch": treating it as stale
    would refuse the very first approval of every review.
    """
    decision = decide_resume_lineage(
        _lineage(),
        authorized_thread_id=A_THREAD,
        operation_thread_id=None,
        operation_phase="PENDING",
    )
    assert decision.allowed
    assert not decision.adopt_operation_lineage


def test_adoption_requires_the_review_lineage_to_be_current_first() -> None:
    """Order matters: a superseded review is refused before adoption is offered.

    Otherwise an operation could be re-pointed at a lineage that is itself
    already historical, which is a slower path to the same defect.
    """
    stale_review = _lineage(
        thread_id=B_THREAD, generation=1, fence=2, authority_generation=2, authority_fence=5
    )
    decision = decide_resume_lineage(
        stale_review,
        authorized_thread_id=B_THREAD,
        operation_thread_id=A_THREAD,
        operation_phase="FAILED_RETRYABLE",
    )
    assert decision.refusal == resume_lineage.REVIEW_LINEAGE_NOT_CURRENT
    assert not decision.adopt_operation_lineage
