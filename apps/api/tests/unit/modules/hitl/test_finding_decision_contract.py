"""PQ-HITL-04A: a finding decision is never itself a final approval."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionAction,
    FindingDecisionDraft,
    FindingDecisionKind,
    stable_finding_id,
)


def _identity() -> CandidateReviewIdentity:
    return CandidateReviewIdentity(
        tenant_id=uuid4(),
        review_row_id=uuid4(),
        document_id=uuid4(),
        document_revision_id=uuid4(),
        artifact_id=uuid4(),
        artifact_version=2,
        artifact_hash="a" * 64,
        generation=3,
        fencing_token=10,
        thread_id="document:doc:g3:f10:analysis",
        checkpoint_id="checkpoint-1",
    )


def test_fingerprint_binds_exact_candidate_and_source_not_display_title() -> None:
    current = _identity()
    first = stable_finding_id(
        current, FindingDecisionKind.RISK, source_item_id="risk-2", ordinal=2
    )
    assert first == stable_finding_id(
        current, FindingDecisionKind.RISK, source_item_id="risk-2", ordinal=2
    )
    assert first != stable_finding_id(
        current.model_copy(update={"artifact_hash": "b" * 64}),
        FindingDecisionKind.RISK,
        source_item_id="risk-2",
        ordinal=2,
    )
    assert first != stable_finding_id(
        current, FindingDecisionKind.CRITIQUE, source_item_id="risk-2", ordinal=2
    )
    assert len(first) == 64


def test_decision_is_provisional_and_tracks_exact_ledger_revision() -> None:
    current = _identity()
    decision = FindingDecisionDraft(
        candidate=current,
        finding_id=stable_finding_id(
            current, FindingDecisionKind.RISK, source_item_id="risk-1", ordinal=0
        ),
        finding_kind=FindingDecisionKind.RISK,
        action=FindingDecisionAction.CONFIRMED,
        reviewer_id="human-reviewer",
        expected_ledger_revision=0,
    )
    assert decision.candidate.fencing_token == 10
    assert decision.expected_ledger_revision == 0
    assert not hasattr(decision, "promote_to_trusted")
    with pytest.raises(ValidationError):
        decision.expected_ledger_revision = 1


@pytest.mark.parametrize(
    "action",
    [
        FindingDecisionAction.CORRECTION_PROPOSED,
        FindingDecisionAction.DISMISSED,
        FindingDecisionAction.NEEDS_INFO,
    ],
)
def test_non_confirmation_actions_require_specific_reason(
    action: FindingDecisionAction,
) -> None:
    with pytest.raises(ValidationError):
        FindingDecisionDraft(
            candidate=_identity(),
            finding_id="a" * 64,
            finding_kind=FindingDecisionKind.CRITIQUE,
            action=action,
            reviewer_id="human-reviewer",
            expected_ledger_revision=0,
        )


def test_correction_requires_new_proposed_text_and_others_forbid_it() -> None:
    with pytest.raises(ValidationError):
        FindingDecisionDraft(
            candidate=_identity(),
            finding_id="a" * 64,
            finding_kind=FindingDecisionKind.RISK,
            action=FindingDecisionAction.CORRECTION_PROPOSED,
            reviewer_id="human",
            expected_ledger_revision=0,
            reason="source contradiction",
        )
    with pytest.raises(ValidationError):
        FindingDecisionDraft(
            candidate=_identity(),
            finding_id="a" * 64,
            finding_kind=FindingDecisionKind.RISK,
            action=FindingDecisionAction.CONFIRMED,
            reviewer_id="human",
            expected_ledger_revision=0,
            proposed_text="fake change",
        )


def test_invalid_identity_or_stale_inputs_rejected_before_write() -> None:
    with pytest.raises(ValidationError):
        CandidateReviewIdentity(
            tenant_id=uuid4(),
            review_row_id=uuid4(),
            document_id=uuid4(),
            document_revision_id=uuid4(),
            artifact_id=uuid4(),
            artifact_version=0,
            artifact_hash="not-a-sha",
            generation=-1,
            fencing_token=-1,
            thread_id="",
            checkpoint_id="",
        )
    with pytest.raises(ValidationError):
        FindingDecisionDraft(
            candidate=_identity(),
            finding_id="not-a-hash",
            finding_kind=FindingDecisionKind.RISK,
            action=FindingDecisionAction.CONFIRMED,
            reviewer_id="human",
            expected_ledger_revision=-1,
        )
