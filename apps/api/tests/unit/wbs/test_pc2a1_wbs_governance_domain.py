"""TS-UT-PC2A1-GOV-001 -- WBS governance domain contracts (ADR-029, #688 amendment, #895).

Pure rules only: the change-set state machine, the node vocabularies, who may decide,
separation of duties, submit validation and the DERIVED authority resolver. The same
rules are enforced again by the database (see the PC-2a.1 integration suite).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.wbs.domain.governance import (
    ALLOWED_TRANSITIONS,
    ActorKind,
    AuthorityState,
    BaselineRef,
    CandidateNode,
    CandidateOriginKind,
    ChangeSetStatus,
    ControlLevel,
    GovernanceRuleError,
    LineageEdge,
    LineageKind,
    can_author,
    can_decide,
    can_withdraw_or_reopen,
    require_transition,
    resolve_authority,
    self_approval,
    validate_control_level,
    validate_decomposition_kind,
    validate_for_submit,
)

S = ChangeSetStatus


# --------------------------------------------------------------------------- state machine
@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.DRAFT, S.SUBMITTED),
        (S.SUBMITTED, S.APPLIED),
        (S.SUBMITTED, S.REJECTED),
        (S.DRAFT, S.WITHDRAWN),
        (S.SUBMITTED, S.WITHDRAWN),
        (S.SUBMITTED, S.DRAFT),
        (S.DRAFT, S.STALE),
        (S.SUBMITTED, S.STALE),
    ],
)
def test_accepted_transitions(current: ChangeSetStatus, target: ChangeSetStatus) -> None:
    require_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.DRAFT, S.APPLIED),  # never apply without submission
        (S.DRAFT, S.REJECTED),
        (S.APPLIED, S.DRAFT),  # terminal states are history
        (S.REJECTED, S.SUBMITTED),
        (S.WITHDRAWN, S.DRAFT),
        (S.STALE, S.SUBMITTED),
        (S.APPLIED, S.APPLIED),
    ],
)
def test_rejected_transitions(current: ChangeSetStatus, target: ChangeSetStatus) -> None:
    with pytest.raises(GovernanceRuleError):
        require_transition(current, target)


def test_there_is_no_approved_but_unapplied_state() -> None:
    assert {status.value for status in ChangeSetStatus} == {
        "DRAFT", "SUBMITTED", "APPLIED", "REJECTED", "WITHDRAWN", "STALE",
    }
    assert all(not targets for status, targets in ALLOWED_TRANSITIONS.items()
               if status in {S.APPLIED, S.REJECTED, S.WITHDRAWN, S.STALE})


# --------------------------------------------------------------------------- vocabularies
def test_control_level_is_vocabulary_only() -> None:
    assert {level.value for level in ControlLevel} == {"none", "control_account", "work_package", "planning_package"}
    assert validate_control_level("work_package") is ControlLevel.WORK_PACKAGE
    with pytest.raises(GovernanceRuleError):
        validate_control_level("cost_account")


def test_control_level_nesting_is_not_hard_coded() -> None:
    # A control account under a control account, or a work package under a work package,
    # is NOT universal-wrong (EPC vs software vs hybrid): methodology rules belong to PC-2b.
    top = CandidateNode(uuid4(), None, 1, "1", "Program", control_level="control_account")
    nested = CandidateNode(uuid4(), top.node_id, 1, "1.1", "Sub-account", control_level="control_account")
    assert validate_for_submit([top, nested], []) == []


@pytest.mark.parametrize("kind", [None, "core:discipline", "core:capability", "pv:substation", "sw:epic"])
def test_decomposition_kind_accepts_core_terms_and_deferred_namespaces(kind: str | None) -> None:
    assert validate_decomposition_kind(kind) == kind


@pytest.mark.parametrize("kind", ["discipline", "Core:area", "core:unknown_term", "core:", ":x", "pv:Sub station"])
def test_decomposition_kind_rejects_malformed_or_unknown_core_terms(kind: str) -> None:
    with pytest.raises(GovernanceRuleError):
        validate_decomposition_kind(kind)


# --------------------------------------------------------------------------- who may decide
@pytest.mark.parametrize(
    ("actor_kind", "role", "allowed"),
    [
        (ActorKind.HUMAN, "admin", True),
        (ActorKind.HUMAN, "user", False),
        (ActorKind.HUMAN, "viewer", False),
        (ActorKind.HUMAN, "api", False),
        (ActorKind.AI, "admin", False),
        (ActorKind.SERVICE, "admin", False),
    ],
)
def test_only_a_human_admin_may_approve_or_reject(actor_kind: ActorKind, role: str, allowed: bool) -> None:
    assert can_decide(actor_kind, role) is allowed


@pytest.mark.parametrize(
    ("actor_kind", "role", "allowed"),
    [
        (ActorKind.HUMAN, "admin", True),
        (ActorKind.HUMAN, "user", True),
        (ActorKind.HUMAN, "viewer", False),
        (ActorKind.HUMAN, "api", False),
        (ActorKind.AI, "user", False),
        (ActorKind.SERVICE, "admin", False),
    ],
)
def test_only_human_users_or_admins_may_submit(actor_kind: ActorKind, role: str, allowed: bool) -> None:
    assert can_author(actor_kind, role) is allowed


def test_only_the_proposer_or_an_admin_may_withdraw_or_reopen() -> None:
    drafter, submitter, colleague = uuid4(), uuid4(), uuid4()
    proposers = (drafter, submitter)
    assert can_withdraw_or_reopen(ActorKind.HUMAN, "user", drafter, proposers=proposers) is True
    assert can_withdraw_or_reopen(ActorKind.HUMAN, "user", submitter, proposers=proposers) is True
    assert can_withdraw_or_reopen(ActorKind.HUMAN, "admin", colleague, proposers=proposers) is True
    assert can_withdraw_or_reopen(ActorKind.HUMAN, "user", colleague, proposers=proposers) is False
    assert can_withdraw_or_reopen(ActorKind.HUMAN, "user", colleague, proposers=(drafter, None)) is False
    # Being the proposer never lifts the human-author requirement.
    assert can_withdraw_or_reopen(ActorKind.AI, "user", drafter, proposers=proposers) is False
    assert can_withdraw_or_reopen(ActorKind.HUMAN, "viewer", drafter, proposers=proposers) is False


def test_separation_of_duties_defaults_to_distinct_approver() -> None:
    submitter = uuid4()
    assert self_approval(submitter=submitter, approver=uuid4(), require_distinct_approver=True) is False
    with pytest.raises(GovernanceRuleError):
        self_approval(submitter=submitter, approver=submitter, require_distinct_approver=True)
    # Only an explicit tenant opt-out allows it, and it is reported for the audit trail.
    assert self_approval(submitter=submitter, approver=submitter, require_distinct_approver=False) is True


# --------------------------------------------------------------------------- submit validation
def _tree() -> list[CandidateNode]:
    a = CandidateNode(uuid4(), None, 1, "1", "Civil", decomposition_kind="core:discipline")
    b = CandidateNode(uuid4(), a.node_id, 1, "1.1", "Earthworks", control_level="work_package",
                      dictionary={"scope_statement": "Cut and fill", "deliverables": ["Platform"]})
    return [a, b]


def test_a_valid_candidate_has_no_violations() -> None:
    assert validate_for_submit(_tree(), []) == []


def test_submit_requires_codes_that_are_present_nfc_and_unique() -> None:
    a, b = _tree()
    missing = CandidateNode(**{**b.__dict__, "code": None})
    assert any("code" in v for v in validate_for_submit([a, missing], []))
    duplicate = CandidateNode(**{**b.__dict__, "code": "1"})
    assert any("duplicate code" in v for v in validate_for_submit([a, duplicate], []))
    nfd = CandidateNode(**{**b.__dict__, "code": "1.1-é"})
    assert any("NFC" in v for v in validate_for_submit([a, nfd], []))


def test_submit_rejects_dangling_parents_and_cycles() -> None:
    a, b = _tree()
    dangling = CandidateNode(**{**b.__dict__, "parent_id": uuid4()})
    assert any("parent" in v for v in validate_for_submit([a, dangling], []))
    cyc_a = CandidateNode(**{**a.__dict__, "parent_id": b.node_id})
    assert any("cycle" in v for v in validate_for_submit([cyc_a, b], []))


def test_submit_rejects_bad_dictionary_and_lineage_targets() -> None:
    a, b = _tree()
    bad = CandidateNode(**{**b.__dict__, "dictionary": {"risk_ids": ["r1"]}})
    assert any("dictionary" in v for v in validate_for_submit([a, bad], []))
    edge = LineageEdge(LineageKind.SPLIT, uuid4(), b.node_id)
    # Split/merge targets are NEW identities: the target must be minted in this change set.
    assert any("minted" in v for v in validate_for_submit([a, b], [edge]))
    minted = CandidateNode(**{**b.__dict__, "origin_kind": CandidateOriginKind.MINTED})
    assert validate_for_submit([a, minted], [edge]) == []
    assert any("not in the candidate" in v
               for v in validate_for_submit([a, minted], [LineageEdge(LineageKind.MERGE, uuid4(), uuid4())]))


# --------------------------------------------------------------------------- authority resolver
def test_authority_no_wbs() -> None:
    authority = resolve_authority(current_baseline=None, live_node_count=0, open_change_sets=0)
    assert authority.state is AuthorityState.NO_WBS
    assert authority.draft_exists is False and authority.display_state == "NO_WBS"
    assert authority.baseline_id is None and authority.tree_digest is None


def test_authority_draft_only_never_claims_approval() -> None:
    authority = resolve_authority(current_baseline=None, live_node_count=0, open_change_sets=2)
    assert authority.state is AuthorityState.NO_WBS
    assert authority.draft_exists is True and authority.display_state == "DRAFT_ONLY"
    assert authority.approved is False


def test_authority_legacy_ungoverned_for_live_rows_without_a_baseline() -> None:
    authority = resolve_authority(current_baseline=None, live_node_count=23, open_change_sets=0)
    assert authority.state is AuthorityState.LEGACY_UNGOVERNED
    assert authority.legacy_node_count == 23 and authority.approved is False


def test_authority_approved_baseline_only_from_a_baseline() -> None:
    applied_at = datetime(2026, 10, 6, tzinfo=UTC)
    baseline = BaselineRef(baseline_id=uuid4(), baseline_no=2, tree_digest="sha256:" + "1" * 64, applied_at=applied_at)
    authority = resolve_authority(current_baseline=baseline, live_node_count=7, open_change_sets=1)
    assert authority.state is AuthorityState.APPROVED_BASELINE and authority.approved is True
    assert (authority.baseline_id, authority.baseline_no, authority.applied_at) == (
        baseline.baseline_id, 2, applied_at)
    assert authority.legacy_node_count == 0 and authority.draft_exists is True
    assert authority.display_state == "APPROVED_BASELINE"
