"""PQ-HITL-04B2: trusted-context writer is ledger-only, never a final approval."""

from uuid import uuid4

import pytest

from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    FindingDecisionIdempotencyConflict,
    FindingDecisionIdentityError,
    FindingDecisionLedgerWriter,
    FindingDecisionRevisionConflict,
)
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionAction,
    FindingDecisionDraft,
    FindingDecisionKind,
    stable_finding_id,
)


class _Rows:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class _Session:
    def __init__(self, *responses):
        self.rows = iter(responses)
        self.calls = []

    async def execute(self, statement, bindings):
        self.calls.append((str(statement), bindings))
        return _Rows(next(self.rows))


def _draft():
    identity = CandidateReviewIdentity(
        tenant_id=uuid4(),
        review_row_id=uuid4(),
        document_id=uuid4(),
        document_revision_id=uuid4(),
        artifact_id=uuid4(),
        artifact_version=2,
        artifact_hash="b" * 64,
        generation=3,
        fencing_token=10,
        thread_id="document:example:g3:f10:analysis",
        checkpoint_id="checkpoint-1",
    )
    return FindingDecisionDraft(
        candidate=identity,
        finding_id=stable_finding_id(
            identity, FindingDecisionKind.RISK, source_item_id="risk-2", ordinal=0
        ),
        finding_kind=FindingDecisionKind.RISK,
        action=FindingDecisionAction.CONFIRMED,
        reviewer_id="authenticated-human",
        expected_ledger_revision=0,
    )


def _locked(draft):
    c = draft.candidate
    return {
        "id": c.review_row_id,
        "project_id": uuid4(),
        "document_id": c.document_id,
        "thread_id": c.thread_id,
        "checkpoint_id": c.checkpoint_id,
        "lineage_generation": c.generation,
        "lineage_fencing_token": c.fencing_token,
        "review_metadata": {
            "trust_candidate_required": True,
            "candidate_binding": {
                "artifact_id": str(c.artifact_id),
                "document_id": str(c.document_id),
                "artifact_version": c.artifact_version,
                "artifact_hash": c.artifact_hash,
            },
        },
    }


@pytest.mark.asyncio
async def test_refuses_wrong_authenticated_tenant_reviewer_or_source_without_db_access():
    draft = _draft()
    for overrides in (
        {"tenant_id": uuid4()},
        {"authenticated_reviewer_id": "impersonator"},
        {"source_item_id": "wrong-risk"},
    ):
        session = _Session()
        args = {
            "tenant_id": draft.candidate.tenant_id,
            "authenticated_reviewer_id": draft.reviewer_id,
            "source_item_id": "risk-2",
            "ordinal": 0,
            "idempotency_key": "request-12345",
            "draft": draft,
        }
        args.update(overrides)
        with pytest.raises(FindingDecisionIdentityError):
            await FindingDecisionLedgerWriter(session).record(**args)
        assert session.calls == []


@pytest.mark.asyncio
async def test_new_decision_checks_row_lock_then_appends_one_provisional_event():
    draft = _draft()
    event_id = uuid4()
    session = _Session(
        _locked(draft),
        None,  # existing idempotency key
        {"ledger_revision": 0},
        {"event_id": event_id, "ledger_revision": 1},
    )
    receipt = await FindingDecisionLedgerWriter(session).record(
        tenant_id=draft.candidate.tenant_id,
        authenticated_reviewer_id=draft.reviewer_id,
        source_item_id="risk-2",
        ordinal=0,
        idempotency_key="request-12345",
        draft=draft,
    )
    assert receipt.event_id == event_id
    assert receipt.ledger_revision == 1
    assert receipt.replayed is False
    assert len(session.calls) == 4
    assert "FOR UPDATE" in session.calls[0][0]
    assert "INSERT INTO public.hitl_finding_decisions" in session.calls[-1][0]
    assert "approve" not in session.calls[-1][0].lower()
    assert "trusted" not in session.calls[-1][0].lower()


@pytest.mark.asyncio
async def test_stale_ledger_revision_fails_before_any_insert():
    draft = _draft()
    session = _Session(
        _locked(draft),
        None,
        {"ledger_revision": 4},
    )
    with pytest.raises(FindingDecisionRevisionConflict):
        await FindingDecisionLedgerWriter(session).record(
            tenant_id=draft.candidate.tenant_id,
            authenticated_reviewer_id=draft.reviewer_id,
            source_item_id="risk-2",
            ordinal=0,
            idempotency_key="request-12345",
            draft=draft,
        )
    assert len(session.calls) == 3
    assert all("INSERT INTO" not in sql for sql, _ in session.calls)


@pytest.mark.asyncio
async def test_same_idempotency_key_replays_only_exact_same_event():
    draft = _draft()
    existing = {
        "event_id": uuid4(),
        "ledger_revision": 1,
        "tenant_id": draft.candidate.tenant_id,
        "review_row_id": draft.candidate.review_row_id,
        "document_id": draft.candidate.document_id,
        "document_revision_id": draft.candidate.document_revision_id,
        "artifact_id": draft.candidate.artifact_id,
        "artifact_version": draft.candidate.artifact_version,
        "artifact_hash": draft.candidate.artifact_hash,
        "generation": draft.candidate.generation,
        "fencing_token": draft.candidate.fencing_token,
        "thread_id": draft.candidate.thread_id,
        "checkpoint_id": draft.candidate.checkpoint_id,
        "finding_id": draft.finding_id,
        "finding_kind": draft.finding_kind.value,
        "action": draft.action.value,
        "reviewer_id": draft.reviewer_id,
        "reason": draft.reason,
        "proposed_text": draft.proposed_text,
        "expected_ledger_revision": draft.expected_ledger_revision,
    }
    params = {
        "tenant_id": draft.candidate.tenant_id,
        "authenticated_reviewer_id": draft.reviewer_id,
        "source_item_id": "risk-2",
        "ordinal": 0,
        "idempotency_key": "request-12345",
        "draft": draft,
    }
    session = _Session(_locked(draft), existing)
    receipt = await FindingDecisionLedgerWriter(session).record(**params)
    assert receipt.replayed is True
    assert receipt.event_id == existing["event_id"]
    assert len(session.calls) == 2

    session = _Session(
        _locked(draft),
        {**existing, "action": "DISMISSED"},
    )
    with pytest.raises(FindingDecisionIdempotencyConflict):
        await FindingDecisionLedgerWriter(session).record(**params)
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_missing_review_row_does_not_write():
    draft = _draft()
    session = _Session(None)
    with pytest.raises(FindingDecisionIdentityError):
        await FindingDecisionLedgerWriter(session).record(
            tenant_id=draft.candidate.tenant_id,
            authenticated_reviewer_id=draft.reviewer_id,
            source_item_id="risk-2",
            ordinal=0,
            idempotency_key="request-12345",
            draft=draft,
        )
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_stale_candidate_rebind_fails_closed_even_for_identical_replay():
    draft = _draft()
    row = _locked(draft)
    row["review_metadata"]["candidate_binding"]["artifact_hash"] = "f" * 64
    session = _Session(row)
    with pytest.raises(FindingDecisionIdentityError):
        await FindingDecisionLedgerWriter(session).record(
            tenant_id=draft.candidate.tenant_id,
            authenticated_reviewer_id=draft.reviewer_id,
            source_item_id="risk-2",
            ordinal=0,
            idempotency_key="request-12345",
            draft=draft,
        )
    assert len(session.calls) == 1

@pytest.mark.asyncio
async def test_stale_fence_or_unbound_candidate_does_not_record_a_review_event():
    draft = _draft()
    for changed in ("fence", "binding", "checkpoint"):
        row = _locked(draft)
        if changed == "fence":
            row["lineage_fencing_token"] += 1
        elif changed == "binding":
            row["review_metadata"]["candidate_binding"] = None
        else:
            row["checkpoint_id"] = "rebound-checkpoint"
        session = _Session(row)
        with pytest.raises(FindingDecisionIdentityError):
            await FindingDecisionLedgerWriter(session).record(
                tenant_id=draft.candidate.tenant_id,
                authenticated_reviewer_id=draft.reviewer_id,
                source_item_id="risk-2",
                ordinal=0,
                idempotency_key="request-12345",
                draft=draft,
            )
        assert len(session.calls) == 1
