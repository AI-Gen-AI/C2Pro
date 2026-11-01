"""S5-03: the pure C+B reconciler. No database, no clock: the meaning of each decision and the digest's guarantees."""

from __future__ import annotations

import dataclasses
import random
from uuid import UUID, uuid4

import pytest

from src.modules.hitl.domain.finding_decision import CandidateReviewIdentity
from src.modules.hitl.domain.finding_decision import FindingDecisionAction as A
from src.modules.hitl.domain.finding_reconciliation import (
    AdvisoryCode,
    BlockerCode,
    CandidateFinding,
    CritiqueCoverage,
    CritiqueEvidence,
    CritiqueMateriality,
    CritiqueObservation,
    CritiqueStatus,
    DerivationCode,
    FindingResolution,
    LedgerEvent,
    ReconciliationInput,
    ReconciliationStatus,
    reconcile,
)

TENANT, REVIEW, DOC, REV, ART, PROJECT = (uuid4() for _ in range(6))
HASH = "a" * 64
IDENTITY = CandidateReviewIdentity(
    tenant_id=TENANT, review_row_id=REVIEW, document_id=DOC, document_revision_id=REV, artifact_id=ART,
    artifact_version=2, artifact_hash=HASH, generation=3, fencing_token=10, thread_id="t", checkpoint_id="c",
)
FINDINGS = tuple(CandidateFinding(i, f"risk-sha256:{i:064d}", f"{i:064x}") for i in range(4))


def event(revision: int, finding: int, action: A, **over) -> LedgerEvent:
    values: dict = {
        "event_id": uuid4(), "ledger_revision": revision, "expected_ledger_revision": revision - 1,
        "finding_id": FINDINGS[finding].finding_id, "finding_kind": "RISK", "action": action, "reviewer_id": "reviewer-1",
        "reason": None if action is A.CONFIRMED else "because", "proposed_text": "new text" if action is A.CORRECTION_PROPOSED else None,
        "recorded_at": None, "tenant_id": TENANT, "review_row_id": REVIEW, "document_id": DOC, "document_revision_id": REV,
        "artifact_id": ART, "artifact_version": 2, "artifact_hash": HASH, "generation": 3, "fencing_token": 10,
    }
    values.update(over)
    return LedgerEvent(**values)


def run(ledger, critiques=(), coverage=CritiqueCoverage.NONE_PRESENT, findings=FINDINGS):
    return reconcile(ReconciliationInput(IDENTITY, PROJECT, findings, ledger, critiques, coverage))


def all_confirmed() -> list[LedgerEvent]:
    return [event(i + 1, i, A.CONFIRMED) for i in range(4)]


def test_every_finding_confirmed_keeps_all_as_valid_decisions_and_is_signable_as_is():
    r = run(all_confirmed())
    assert r.status is ReconciliationStatus.CONSISTENT and r.signable_as_is
    assert [o.resolution for o in r.outcomes] == [FindingResolution.RETAINED] * 4
    assert all(o.decisive and o.decisive.reviewer_id == "reviewer-1" and o.decisive.event_id for o in r.outcomes), "evidence kept"
    assert r.retained == FINDINGS and r.excluded == () and r.blockers == () and r.derivations == ()
    assert r.ledger_revision == 4


def test_dismissed_is_excluded_from_the_effective_content_keeps_its_history_and_requires_a_derived_candidate():
    ledger = all_confirmed()[:3] + [event(4, 3, A.DISMISSED)]
    r = run(ledger)
    assert r.retained == FINDINGS[:3] and r.excluded == (FINDINGS[3],)
    assert [d.code for d in r.derivations] == [DerivationCode.DISMISSED_EXCLUSION]
    assert not r.signable_as_is, "the content to sign is a DERIVED candidate, not this one"
    excluded = next(o for o in r.outcomes if o.finding_id == FINDINGS[3].finding_id)
    assert excluded.decisive and excluded.decisive.reason == "because" and len(excluded.history) == 1
    assert r.effective_content_digest != run(all_confirmed()).effective_content_digest


def test_needs_info_blocks_until_a_later_decision_supersedes_it_and_the_history_is_not_lost():
    ledger = all_confirmed()[:3] + [event(4, 3, A.NEEDS_INFO)]
    blocked = run(ledger)
    assert [b.code for b in blocked.blockers] == [BlockerCode.NEEDS_INFO] and not blocked.signable_as_is
    resolved = run([*ledger, event(5, 3, A.CONFIRMED)])
    assert resolved.blockers == () and resolved.signable_as_is
    history = next(o for o in resolved.outcomes if o.finding_id == FINDINGS[3].finding_id).history
    assert [h.action for h in history] == [A.NEEDS_INFO, A.CONFIRMED], "the superseded decision stays on record"
    dismissed_after = run([*ledger, event(5, 3, A.DISMISSED)])
    assert dismissed_after.blockers == () and [d.code for d in dismissed_after.derivations] == [DerivationCode.DISMISSED_EXCLUSION]


def test_a_proposed_correction_announces_a_new_candidate_and_is_never_applied():
    ledger = all_confirmed()[:3] + [event(4, 3, A.CORRECTION_PROPOSED, proposed_text="reworded")]
    r = run(ledger)
    assert [d.code for d in r.derivations] == [DerivationCode.CORRECTION_PROPOSED] and not r.signable_as_is
    assert FINDINGS[3] not in r.retained and FINDINGS[3] not in r.excluded, "neither silently kept nor removed"
    outcome = r.outcomes[3]
    assert outcome.resolution is FindingResolution.CORRECTION_PENDING and outcome.proposed_text_sha256
    other = run(all_confirmed()[:3] + [event(4, 3, A.CORRECTION_PROPOSED, proposed_text="different")])
    assert other.digest != r.digest, "the exact text of the correction is part of what is reconciled"


def test_a_finding_without_a_decision_blocks_fail_closed():
    r = run(all_confirmed()[:3])
    assert [b.code for b in r.blockers] == [BlockerCode.UNDECIDED_FINDING] and r.outcomes[3].resolution is FindingResolution.UNDECIDED
    assert not r.signable_as_is
    assert not run([]).signable_as_is and len(run([]).blockers) == 4


def test_a_candidate_with_no_findings_is_vacuously_signable():
    r = run([], findings=())
    assert r.signable_as_is and r.retained == () and r.ledger_revision == 0


@pytest.mark.parametrize(
    ("materiality", "evidence", "status", "blocks", "advisory"),
    [
        (CritiqueMateriality.MATERIAL, CritiqueEvidence.VERIFIED, CritiqueStatus.OPEN, True, None),
        (CritiqueMateriality.MATERIAL, CritiqueEvidence.VERIFIED, CritiqueStatus.RESOLVED, False, None),
        (CritiqueMateriality.MATERIAL, CritiqueEvidence.UNVERIFIED, CritiqueStatus.OPEN, False, AdvisoryCode.MATERIAL_CRITIQUE_WITHOUT_VERIFIED_EVIDENCE),
        (CritiqueMateriality.NON_MATERIAL, CritiqueEvidence.VERIFIED, CritiqueStatus.OPEN, False, AdvisoryCode.NON_MATERIAL_CRITIQUE),
        (CritiqueMateriality.NON_MATERIAL, CritiqueEvidence.UNVERIFIED, CritiqueStatus.RESOLVED, False, None),
    ],
)
def test_a_critique_blocks_only_when_material_verified_and_open(materiality, evidence, status, blocks, advisory):
    critique = CritiqueObservation("obs-1", materiality, evidence, status)
    r = run(all_confirmed(), (critique,), CritiqueCoverage.TYPED_OBSERVATIONS)
    assert (BlockerCode.MATERIAL_CRITIQUE_UNRESOLVED in [b.code for b in r.blockers]) is blocks
    assert r.signable_as_is is (not blocks)
    assert ([a.code for a in r.advisories if a.code is not AdvisoryCode.STALE_DECISIONS_IGNORED] == [advisory]) if advisory else not r.advisories


def test_unstructured_critique_is_declared_not_evaluated_and_never_a_silent_pass_or_a_blanket_block():
    r = run(all_confirmed(), (), CritiqueCoverage.UNSTRUCTURED_NOT_EVALUATED)
    assert r.critique_coverage is CritiqueCoverage.UNSTRUCTURED_NOT_EVALUATED
    assert [a.code for a in r.advisories] == [AdvisoryCode.CRITIQUE_NOT_EVALUABLE] and r.signable_as_is
    assert r.digest != run(all_confirmed()).digest, "the coverage is part of what is reconciled"


def test_the_digest_is_deterministic_whatever_the_order_the_ledger_arrives_in():
    ledger = all_confirmed()[:3] + [event(4, 3, A.NEEDS_INFO), event(5, 3, A.CONFIRMED)]
    reference = run(ledger)
    for seed in range(20):
        shuffled = list(ledger)
        random.Random(seed).shuffle(shuffled)
        assert run(shuffled).digest == reference.digest
    assert run(ledger).receipt() == reference.receipt()


def test_any_new_decision_or_changed_input_changes_the_digest_so_a_stale_receipt_is_detectable():
    ledger = all_confirmed()
    base = run(ledger).digest
    assert run([*ledger, event(5, 0, A.CONFIRMED)]).digest != base, "a later decision, even a repeat"
    assert run([*ledger[:3], dataclasses.replace(ledger[3], action=A.DISMISSED, reason="x")]).digest != base
    assert reconcile(ReconciliationInput(IDENTITY.model_copy(update={"generation": 4}), PROJECT, FINDINGS, ledger)).digest != base
    assert reconcile(ReconciliationInput(IDENTITY, uuid4(), FINDINGS, ledger)).digest != base, "another project"
    assert run(ledger, (CritiqueObservation("o", CritiqueMateriality.MATERIAL, CritiqueEvidence.VERIFIED, CritiqueStatus.OPEN),)).digest != base


def test_decisions_on_another_candidate_or_generation_are_ignored_and_reported_never_applied():
    obsolete = event(1, 0, A.DISMISSED, artifact_hash="b" * 64)  # taken on the superseded candidate
    ledger = [obsolete] + [event(i + 2, i, A.CONFIRMED) for i in range(4)]
    r = run(ledger)
    assert r.status is ReconciliationStatus.CONSISTENT and r.signable_as_is, "the obsolete dismissal does not exclude anything"
    assert r.retained == FINDINGS and r.stale_event_ids == (obsolete.event_id,)
    assert AdvisoryCode.STALE_DECISIONS_IGNORED in [a.code for a in r.advisories]
    older_generation = event(1, 0, A.NEEDS_INFO, generation=2)
    assert run([older_generation] + [event(i + 2, i, A.CONFIRMED) for i in range(4)]).signable_as_is


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("gap", "LEDGER_REVISIONS_NOT_CONTIGUOUS_FROM_1"),
        ("duplicate_revision", "LEDGER_DUPLICATE_REVISION"),
        ("cas_broken", "LEDGER_CAS_CHAIN_BROKEN_AT"),
        ("foreign_tenant", "LEDGER_EVENT_OF_ANOTHER_TENANT_OR_REVIEW"),
        ("foreign_review", "LEDGER_EVENT_OF_ANOTHER_TENANT_OR_REVIEW"),
        ("unknown_finding", "DECISION_ON_A_FINDING_OUTSIDE_THE_CANDIDATE"),
        ("critique_kind", "DECISION_ON_A_FINDING_OUTSIDE_THE_CANDIDATE"),
        ("duplicate_event_id", "LEDGER_DUPLICATE_EVENT_ID"),
    ],
)
def test_an_incomplete_unordered_or_foreign_ledger_is_inconsistent_and_concludes_nothing(case, code):
    ledger = all_confirmed()
    if case == "gap":
        ledger = [ledger[0], ledger[2], ledger[3]]
    elif case == "duplicate_revision":
        ledger[1] = dataclasses.replace(ledger[1], ledger_revision=1, expected_ledger_revision=0)
    elif case == "cas_broken":
        ledger[2] = dataclasses.replace(ledger[2], expected_ledger_revision=0)
    elif case == "foreign_tenant":
        ledger[1] = dataclasses.replace(ledger[1], tenant_id=uuid4())
    elif case == "foreign_review":
        ledger[1] = dataclasses.replace(ledger[1], review_row_id=uuid4())
    elif case == "unknown_finding":
        ledger[1] = dataclasses.replace(ledger[1], finding_id="f" * 64)
    elif case == "critique_kind":
        ledger[1] = dataclasses.replace(ledger[1], finding_kind="CRITIQUE")
    else:
        ledger[1] = dataclasses.replace(ledger[1], event_id=ledger[0].event_id)
    r = run(ledger)
    assert r.status is ReconciliationStatus.INCONSISTENT and not r.signable_as_is
    assert any(i.startswith(code) for i in r.inconsistencies), r.inconsistencies
    assert r.outcomes == () and r.retained == () and r.blockers == (), "nothing is concluded from an untrustworthy ledger"


def test_the_receipt_carries_the_exact_identity_the_signature_must_match():
    r = run(all_confirmed())
    receipt = r.receipt()
    assert (receipt.review_row_id, receipt.project_id, receipt.artifact_id, receipt.artifact_version) == (REVIEW, PROJECT, ART, 2)
    assert (receipt.artifact_hash, receipt.generation, receipt.fencing_token, receipt.ledger_revision) == (HASH, 3, 10, 4)
    assert receipt.digest == r.digest and receipt.signable_as_is and receipt.policy_version == "s5-03/v1"
    assert isinstance(receipt.review_row_id, UUID)
