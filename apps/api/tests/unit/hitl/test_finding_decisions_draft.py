"""PQ-HITL-04A: in-memory decision drafting, NOT trusted settlement."""
from dataclasses import replace
from uuid import uuid4

import pytest

from src.analysis.domain.trust import CandidateBinding
from src.modules.hitl.domain.finding_decisions import (
    DecisionAction,
    DecisionConflict,
    FindingDecisionDraft,
    ProposedFindingDecision,
    ReviewCandidateScope,
    apply_finding_decision,
)


def _scope() -> ReviewCandidateScope:
    return ReviewCandidateScope(
        tenant_id=uuid4(),
        review_row_id=uuid4(),
        binding=CandidateBinding(
            artifact_id=uuid4(),
            document_id=uuid4(),
            artifact_version=2,
            artifact_hash="c" * 64,
        ),
        generation=3,
        fencing_token=10,
        thread_id="document:test:g3:f10:analysis",
        checkpoint_id=uuid4(),
    )


def _command(
    scope: ReviewCandidateScope,
    finding_id: str = "risk-1",
    action: DecisionAction = DecisionAction.CONFIRM,
    expected_revision: int = 0,
    **kwargs: object,
) -> ProposedFindingDecision:
    return ProposedFindingDecision(
        scope=scope,
        finding_id=finding_id,
        action=action,
        reason="Verified against clause 5.2" if action != DecisionAction.CORRECT else "Propose correct obligation",
        reviewer_id=uuid4(),
        expected_revision=expected_revision,
        idempotency_key="key-1",
        **kwargs,
    )


def test_one_finding_decision_does_not_settle_or_promote_a_candidate() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1", "risk-2"}))
    result = apply_finding_decision(draft, _command(scope))

    assert result.revision == 1
    assert len(result.entries) == 1
    assert result.ready_for_final_authority_check is False
    assert result.scope.binding.artifact_hash == "c" * 64
    assert draft.entries == ()
    assert draft.revision == 0


def test_idempotent_replay_does_not_append_a_second_decision() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1"}))
    request = _command(scope)
    once = apply_finding_decision(draft, request)
    assert apply_finding_decision(once, request) is once

    with pytest.raises(DecisionConflict):
        apply_finding_decision(once, replace(request, reason="Different decision"))


def test_wrong_tenant_hash_or_fence_always_fails_closed() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1"}))
    for wrong_scope in [
        replace(scope, tenant_id=uuid4()),
        replace(scope, binding=replace(scope.binding, artifact_hash="d" * 64)),
        replace(scope, fencing_token=scope.fencing_token + 1),
    ]:
        with pytest.raises(DecisionConflict):
            apply_finding_decision(draft, _command(wrong_scope))


def test_outdated_decision_revision_cannot_overwrite_newer_draft() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1", "risk-2"}))
    updated = apply_finding_decision(draft, _command(scope))

    with pytest.raises(DecisionConflict):
        apply_finding_decision(
            updated, replace(_command(scope, finding_id="risk-2"), idempotency_key="key-2")
        )


def test_all_required_resolved_allows_only_a_request_for_final_authority_check() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1", "risk-2"}))
    first = apply_finding_decision(draft, _command(scope))
    second = apply_finding_decision(
        first,
        replace(
            _command(scope, finding_id="risk-2", action=DecisionAction.DISMISS),
            expected_revision=1,
            idempotency_key="key-2",
        ),
    )
    assert second.ready_for_final_authority_check is True
    assert len(second.entries) == 2


def test_correction_is_provisional_and_requires_a_new_candidate() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1"}))
    corrected = apply_finding_decision(
        draft,
        _command(
            scope,
            action=DecisionAction.CORRECT,
            proposed_correction={"obligation": "Contractor pays, fourteen (14) days"},
        ),
    )
    assert corrected.ready_for_final_authority_check is False
    assert corrected.requires_new_candidate is True

    with pytest.raises(ValueError):
        apply_finding_decision(draft, _command(scope, action=DecisionAction.CORRECT))



def test_correction_cannot_be_erased_by_a_later_confirm_on_same_candidate() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1"}))
    corrected = apply_finding_decision(
        draft,
        _command(scope, action=DecisionAction.CORRECT, proposed_correction={"time_days": 14}),
    )
    followup = apply_finding_decision(
        corrected,
        replace(
            _command(scope),
            expected_revision=1,
            idempotency_key="key-2",
        ),
    )
    assert followup.requires_new_candidate is True
    assert followup.ready_for_final_authority_check is False

def test_missing_reason_and_unknown_finding_are_refused() -> None:
    scope = _scope()
    draft = FindingDecisionDraft(scope=scope, required_finding_ids=frozenset({"risk-1"}))
    with pytest.raises(ValueError):
        apply_finding_decision(draft, replace(_command(scope), reason=" "))
    with pytest.raises(DecisionConflict):
        apply_finding_decision(draft, _command(scope, finding_id="not-in-candidate"))
