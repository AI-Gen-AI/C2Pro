"""#940C4: exact candidate is reconstructed by the application, not supplied by caller."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.domain.trust import artifact_digest
from src.core.auth.models import UserRole
from src.modules.hitl.application.finding_review_authorization import (
    FindingDecisionSubmission,
    FindingReviewerNotAuthorized,
)
from src.modules.hitl.application.record_finding_decision_use_case import (
    RecordFindingDecisionUseCase,
)
from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    FindingDecisionIdentityError,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id


_RISK = {"title": "Rectification", "description": "14 days at contractor cost"}
_PAYLOAD = {"extracted_risks": [_RISK]}
_HASH = artifact_digest(_PAYLOAD)
_SOURCE = risk_source_item_id(_RISK)


class _Result:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class _Session:
    def __init__(self, *rows):
        self.rows = iter(rows)
        self.calls = []

    async def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return _Result(next(self.rows))


def _case():
    tenant, reviewer, review, doc, revision, artifact, project = (uuid4() for _ in range(7))
    user = SimpleNamespace(id=reviewer, tenant_id=tenant, role=UserRole.USER, is_active=True)
    payload = FindingDecisionSubmission(
        artifact_id=artifact,
        artifact_version=2,
        artifact_hash=_HASH,
        document_revision_id=revision,
        generation=3,
        fencing_token=10,
        source_item_id=_SOURCE,
        ordinal=0,
        action="CONFIRMED",
        expected_ledger_revision=0,
        idempotency_key="review-key-12345",
    )
    metadata = {"trust_candidate_required": True, "candidate_binding": {
        "artifact_id": str(artifact), "document_id": str(doc),
        "artifact_version": 2, "artifact_hash": _HASH,
    }}
    row = {
        "id": review, "project_id": project, "document_id": doc,
        "thread_id": "document:example:g3:f10:analysis", "checkpoint_id": "cp-1",
        "lineage_generation": 3, "lineage_fencing_token": 10,
        "review_metadata": metadata,
    }
    return tenant, user, review, payload, row


@pytest.mark.asyncio
async def test_nonhuman_or_mismatched_tenant_denied_before_database_use():
    tenant, user, review, payload, row = _case()
    for spoofed in (
        SimpleNamespace(**{**vars(user), "role": UserRole.API}),
        SimpleNamespace(**{**vars(user), "role": UserRole.VIEWER}),
        SimpleNamespace(**{**vars(user), "tenant_id": uuid4()}),
    ):
        session = _Session()
        with pytest.raises(FindingReviewerNotAuthorized):
            await RecordFindingDecisionUseCase(session).execute(
                tenant_id=tenant, user=spoofed, review_row_id=review, submission=payload
            )
        assert session.calls == []


@pytest.mark.asyncio
async def test_stale_candidate_digest_and_lineage_are_denied_before_append():
    tenant, user, review, payload, row = _case()
    for changed in ("artifact_hash", "lineage_fencing_token", "trust_candidate_required"):
        original = _case()[4]
        # Always mutate the actual scoped row, not a second randomly generated fixture.
        original = {**row, "review_metadata": {
            **row["review_metadata"],
            "candidate_binding": {**row["review_metadata"]["candidate_binding"]},
        }}
        if changed == "artifact_hash":
            original["review_metadata"]["candidate_binding"]["artifact_hash"] = "f" * 64
        elif changed == "lineage_fencing_token":
            original["lineage_fencing_token"] = 11
        else:
            original["review_metadata"]["trust_candidate_required"] = False
        session = _Session(original)
        with pytest.raises(FindingDecisionIdentityError):
            await RecordFindingDecisionUseCase(session).execute(
                tenant_id=tenant, user=user, review_row_id=review, submission=payload
            )
        assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_missing_review_does_not_make_up_a_candidate():
    tenant, user, review, payload, _ = _case()
    session = _Session(None)
    with pytest.raises(FindingDecisionIdentityError):
        await RecordFindingDecisionUseCase(session).execute(
            tenant_id=tenant, user=user, review_row_id=review, submission=payload
        )
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_provisional_event_uses_authenticated_user_and_real_review_identity():
    tenant, user, review, payload, row = _case()
    event_id = uuid4()
    session = _Session(
        row,
        row,  # writer FOR UPDATE lock
        {"payload": _PAYLOAD},
        None,
        {"ledger_revision": 0},
        {"event_id": event_id, "ledger_revision": 1},
    )
    receipt = await RecordFindingDecisionUseCase(session).execute(
        tenant_id=tenant, user=user, review_row_id=review, submission=payload
    )
    assert receipt.event_id == event_id
    assert receipt.ledger_revision == 1
    assert receipt.replayed is False
    assert len(session.calls) == 6
    sql, values = session.calls[-1]
    assert "INSERT INTO public.hitl_finding_decisions" in sql
    assert values["reviewer_id"] == str(user.id)
    assert values["created_by"] == str(user.id)
    assert values["tenant_id"] == tenant
    assert values["review_row_id"] == review
    assert values["document_id"] == row["document_id"]
    assert values["source_item_id"] == _SOURCE
    assert "TRUSTED" not in sql
