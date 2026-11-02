"""S5 Vn+1: the pure materializer of a derived candidate. No database, no clock, no AI.

What is proven: exclusions and corrections are applied ONLY as the S5-03 contract says (DISMISSED leaves the finding out,
CORRECTION_PROPOSED replaces the one ratified field with the reviewer's own text, CONFIRMED is carried untouched); the
source risks are never mutated; an incomplete or inconsistent reconciliation is not derivable; the provenance names the
source candidate, the reconciliation digest and every decision it rests on.
"""

from __future__ import annotations

import copy
from uuid import uuid4

import pytest

from src.modules.hitl.domain.derived_candidate import (
    CORRECTION_TARGET_FIELD,
    DERIVATION_POLICY_VERSION,
    NotDerivable,
    derive_content,
    provenance_entry,
    requires_corrections,
)
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionKind,
    stable_finding_id,
)
from src.modules.hitl.domain.finding_decision import FindingDecisionAction as A
from src.modules.hitl.domain.finding_reconciliation import (
    CandidateFinding,
    LedgerEvent,
    ReconciliationInput,
    reconcile,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id

TENANT, REVIEW, DOC, REV, ART, PROJECT = (uuid4() for _ in range(6))
HASH = "a" * 64
IDENTITY = CandidateReviewIdentity(
    tenant_id=TENANT, review_row_id=REVIEW, document_id=DOC, document_revision_id=REV, artifact_id=ART,
    artifact_version=2, artifact_hash=HASH, generation=3, fencing_token=10, thread_id="t", checkpoint_id="c",
)
RISKS = [
    {"title": f"Risk {i}", "description": f"Description {i}", "category": "TIME", "severity": "HIGH", "clause_ref": f"Clause {i}", "confidence": 0.9}
    for i in range(4)
]
FINDINGS = tuple(
    CandidateFinding(
        i, risk_source_item_id(risk),
        stable_finding_id(IDENTITY, FindingDecisionKind.RISK, source_item_id=risk_source_item_id(risk), ordinal=i),
    )
    for i, risk in enumerate(RISKS)
)


def event(revision: int, finding: int, action: A, **over) -> LedgerEvent:
    values: dict = {
        "event_id": uuid4(), "ledger_revision": revision, "expected_ledger_revision": revision - 1,
        "finding_id": FINDINGS[finding].finding_id, "finding_kind": "RISK", "action": action, "reviewer_id": "reviewer-1",
        "reason": None if action is A.CONFIRMED else "because",
        "proposed_text": "Corrected description." if action is A.CORRECTION_PROPOSED else None,
        "recorded_at": None, "tenant_id": TENANT, "review_row_id": REVIEW, "document_id": DOC, "document_revision_id": REV,
        "artifact_id": ART, "artifact_version": 2, "artifact_hash": HASH, "generation": 3, "fencing_token": 10,
    }
    values.update(over)
    return LedgerEvent(**values)


def decide(*actions: A, **texts: str):
    ledger = [event(i + 1, i, a, **({"proposed_text": texts[str(i)]} if str(i) in texts else {})) for i, a in enumerate(actions)]
    result = reconcile(ReconciliationInput(IDENTITY, PROJECT, FINDINGS, ledger))
    return result, ledger


def test_a_dismissed_finding_is_left_out_and_everything_else_is_carried_untouched() -> None:
    result, ledger = decide(A.CONFIRMED, A.DISMISSED, A.CONFIRMED, A.CONFIRMED)
    source = copy.deepcopy(RISKS)
    content = derive_content(source, result, ledger)
    assert [r["title"] for r in content.risks] == ["Risk 0", "Risk 2", "Risk 3"]
    assert content.risks[0] == RISKS[0] and content.risks[2] == RISKS[3], "retained risks are byte-for-byte the source's"
    assert content.retained == (0, 2, 3) and [e.ordinal for e in content.excluded] == [1] and content.corrected == ()
    assert source == RISKS, "the source payload is never mutated"
    assert content.excluded[0].decision_event_id == ledger[1].event_id


def test_a_correction_replaces_only_the_ratified_field_with_the_reviewers_own_text() -> None:
    result, ledger = decide(A.CONFIRMED, A.CORRECTION_PROPOSED, A.CONFIRMED, A.CONFIRMED, **{"1": "  The period is 14 days.  "})
    content = derive_content(RISKS, result, ledger)
    corrected = content.risks[1]
    assert corrected[CORRECTION_TARGET_FIELD] == "The period is 14 days.", "the human's text, trimmed, nothing generated"
    assert {k: v for k, v in corrected.items() if k != CORRECTION_TARGET_FIELD} == {k: v for k, v in RISKS[1].items() if k != CORRECTION_TARGET_FIELD}
    assert RISKS[1][CORRECTION_TARGET_FIELD] == "Description 1", "the source is untouched"
    assert len(content.risks) == 4 and [c.ordinal for c in content.corrected] == [1] and content.excluded == ()
    assert requires_corrections(result)


def test_exclusion_and_correction_together_keep_the_source_order() -> None:
    result, ledger = decide(A.CORRECTION_PROPOSED, A.CONFIRMED, A.DISMISSED, A.CONFIRMED)
    content = derive_content(RISKS, result, ledger)
    assert [r["title"] for r in content.risks] == ["Risk 0", "Risk 1", "Risk 3"] and content.changes == 2


def test_the_latest_decision_wins_so_a_superseded_dismissal_is_carried() -> None:
    first, _ = decide(A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED)
    ledger = [event(i + 1, i, A.CONFIRMED) for i in range(4)]
    ledger.append(event(5, 3, A.DISMISSED))
    ledger.append(event(6, 3, A.CONFIRMED))
    result = reconcile(ReconciliationInput(IDENTITY, PROJECT, FINDINGS, ledger))
    assert result.signable_as_is, "nothing to derive once the dismissal is superseded"
    with pytest.raises(NotDerivable, match="needs no derived candidate"):
        derive_content(RISKS, result, ledger)
    assert first.derivations, "while the dismissal stands a derived candidate is required"


@pytest.mark.parametrize(
    ("actions", "reason"),
    [
        ((A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.NEEDS_INFO), "blockers"),
        ((A.CONFIRMED, A.DISMISSED, A.CONFIRMED), "blockers"),  # the fourth finding is undecided
        ((A.CONFIRMED,) * 4, "needs no derived candidate"),
    ],
)
def test_an_incomplete_or_already_signable_reconciliation_is_not_derivable(actions, reason) -> None:
    result, ledger = decide(*actions)
    with pytest.raises(NotDerivable, match=reason):
        derive_content(RISKS, result, ledger)


def test_an_inconsistent_ledger_derives_nothing() -> None:
    ledger = [event(1, 0, A.DISMISSED), event(3, 1, A.CONFIRMED)]  # a gap in the ledger revisions
    result = reconcile(ReconciliationInput(IDENTITY, PROJECT, FINDINGS, ledger))
    with pytest.raises(NotDerivable, match="inconsistent"):
        derive_content(RISKS, result, ledger)


def test_a_source_payload_that_is_not_the_reconciled_candidate_is_refused() -> None:
    result, ledger = decide(A.CONFIRMED, A.DISMISSED, A.CONFIRMED, A.CONFIRMED)
    tampered = copy.deepcopy(RISKS)
    tampered[2]["title"] = "Substituted"
    with pytest.raises(NotDerivable, match="does not match the source payload"):
        derive_content(tampered, result, ledger)
    with pytest.raises(NotDerivable, match="not the findings of the source payload"):
        derive_content(RISKS[:3], result, ledger)


def test_the_provenance_names_the_source_the_reconciliation_and_every_decision() -> None:
    result, ledger = decide(A.CONFIRMED, A.DISMISSED, A.CORRECTION_PROPOSED, A.CONFIRMED)
    content = derive_content(RISKS, result, ledger)
    new_artifact, actor = uuid4(), uuid4()
    entry = provenance_entry(
        result=result, content=content, source_document_revision_id=REV, derived_artifact_id=new_artifact,
        derived_artifact_version=3, derived_artifact_hash="b" * 64, derived_by=actor,
    )
    assert entry["policy"] == DERIVATION_POLICY_VERSION and entry["derived_state"] == "PROPOSED"
    assert (entry["source_artifact_id"], entry["source_artifact_version"], entry["source_artifact_hash"]) == (str(ART), 2, HASH)
    assert entry["source_document_revision_id"] == str(REV) and entry["reconciliation_digest"] == result.digest
    assert entry["source_ledger_revision"] == 4 and entry["derived_by"] == str(actor)
    assert (entry["derived_artifact_id"], entry["derived_artifact_version"], entry["derived_artifact_hash"]) == (str(new_artifact), 3, "b" * 64)
    assert entry["excluded"][0]["decision_event_id"] == str(ledger[1].event_id)
    assert entry["corrected"][0]["decision_event_id"] == str(ledger[2].event_id) and entry["retained"] == [0, 3]
    assert entry["corrected"][0]["original_sha256"] != entry["corrected"][0]["proposed_sha256"]
    assert "Corrected description." not in str(entry), "the provenance carries digests, not a second copy of the content"


def test_the_derivation_is_deterministic() -> None:
    result, ledger = decide(A.CONFIRMED, A.DISMISSED, A.CONFIRMED, A.CONFIRMED)
    assert derive_content(RISKS, result, ledger) == derive_content(copy.deepcopy(RISKS), result, list(reversed(ledger)))
