"""S5: read model of the findings of a pending review, and the HTTP mapping of the decision use case."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.analysis.domain.trust import artifact_digest
from src.core.auth.models import UserRole
from src.modules.hitl.adapters.http import finding_decision_router as router
from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    FindingDecisionIdempotencyConflict,
    FindingDecisionIdentityError,
    FindingDecisionRevisionConflict,
    FindingDecisionWriteReceipt,
)
from src.modules.hitl.application.finding_review_authorization import (
    FindingDecisionSubmission,
    FindingReviewerNotAuthorized,
)
from src.modules.hitl.application.review_findings_view import (
    ReviewFindingsUnavailable,
    ReviewFindingsViewService,
)
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionKind,
    stable_finding_id,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id

_RISKS = [
    {"title": "Penalty", "description": "30 days", "category": "TIME", "severity": "high", "raw_model_noise": "x"},
    {"title": "Price", "description": "revised", "category": "BUDGET"},
]
_PAYLOAD = {"extracted_risks": _RISKS}
_HASH = artifact_digest(_PAYLOAD)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class _Session:
    def __init__(self, *results):
        self.results = iter(results)

    async def execute(self, statement, params=None):
        return _Result(next(self.results))


def _world(**binding_overrides):
    tenant, reviewer, row_id, doc, revision, artifact, project = (uuid4() for _ in range(7))
    user = SimpleNamespace(id=reviewer, tenant_id=tenant, role=UserRole.USER, is_active=True)
    binding = {
        "artifact_id": str(artifact),
        "document_id": str(doc),
        "artifact_version": 2,
        "artifact_hash": _HASH,
        **binding_overrides,
    }
    review = {
        "id": row_id,
        "project_id": project,
        "document_id": doc,
        "thread_id": "document:x:g3:f10:analysis",
        "checkpoint_id": "cp-1",
        "lineage_generation": 3,
        "lineage_fencing_token": 10,
        "review_metadata": {"trust_candidate_required": True, "candidate_binding": binding},
    }
    candidate = {"document_revision_id": revision, "payload": _PAYLOAD, "generation": 3, "fencing_token": 10}
    identity = CandidateReviewIdentity(
        tenant_id=tenant,
        review_row_id=row_id,
        document_id=doc,
        document_revision_id=revision,
        artifact_id=artifact,
        artifact_version=2,
        artifact_hash=_HASH,
        generation=3,
        fencing_token=10,
        thread_id=review["thread_id"],
        checkpoint_id="cp-1",
    )
    return tenant, user, row_id, review, candidate, identity


def _finding_id(identity, ordinal):
    return stable_finding_id(
        identity, FindingDecisionKind.RISK, source_item_id=risk_source_item_id(_RISKS[ordinal]), ordinal=ordinal
    )


@pytest.mark.asyncio
async def test_the_view_lists_risks_with_pins_and_reviewer_facing_fields_only() -> None:
    tenant, user, row_id, review, candidate, identity = _world()
    event = {
        "event_id": uuid4(),
        "ledger_revision": 1,
        "finding_id": _finding_id(identity, 1),
        "action": "DISMISSED",
        "reason": "waived",
        "proposed_text": None,
        "reviewer_id": str(user.id),
        "recorded_at": datetime.now(UTC),
    }
    view = await ReviewFindingsViewService(_Session([review], [candidate], [event])).execute(
        tenant_id=tenant, user=user, review_row_id=row_id
    )

    assert (view.artifact_version, view.artifact_hash, view.generation, view.fencing_token) == (2, _HASH, 3, 10)
    assert view.ledger_revision == 1
    assert [f.ordinal for f in view.findings] == [0, 1]
    assert "raw_model_noise" not in view.findings[0].risk
    assert view.findings[0].risk == {"title": "Penalty", "description": "30 days", "category": "TIME", "severity": "high"}
    assert view.findings[0].current is None
    assert view.findings[1].current is not None and view.findings[1].current.action == "DISMISSED"


@pytest.mark.asyncio
async def test_non_human_or_foreign_tenant_is_denied_before_any_query() -> None:
    tenant, user, row_id, *_ = _world()
    for spoofed in (
        SimpleNamespace(**{**vars(user), "role": UserRole.VIEWER}),
        SimpleNamespace(**{**vars(user), "tenant_id": uuid4()}),
    ):
        with pytest.raises(FindingReviewerNotAuthorized):
            await ReviewFindingsViewService(_Session()).execute(tenant_id=tenant, user=spoofed, review_row_id=row_id)


@pytest.mark.asyncio
async def test_unknown_unbound_or_changed_candidates_are_unavailable() -> None:
    tenant, user, row_id, review, candidate, _ = _world()

    async def run(*results):
        return await ReviewFindingsViewService(_Session(*results)).execute(
            tenant_id=tenant, user=user, review_row_id=row_id
        )

    with pytest.raises(ReviewFindingsUnavailable):  # no pending review of this tenant
        await run([])
    structured = {**review, "review_metadata": {**review["review_metadata"], "trust_kind": "structured_source"}}
    with pytest.raises(ReviewFindingsUnavailable):  # a Budget/Schedule trust review has no findings
        await run([structured])
    unbound = {**review, "review_metadata": {"trust_candidate_required": False}}
    with pytest.raises(ReviewFindingsUnavailable):
        await run([unbound])
    with pytest.raises(ReviewFindingsUnavailable):  # candidate no longer proposed / authority moved
        await run([review], [])
    with pytest.raises(ReviewFindingsUnavailable):  # payload no longer hashes to the pinned digest
        await run([review], [{**candidate, "payload": {"extracted_risks": []}}])
    with pytest.raises(ReviewFindingsUnavailable):  # review lineage differs from the live authority
        await run([review], [{**candidate, "generation": 4}])
    malformed = {**review, "review_metadata": {**review["review_metadata"], "candidate_binding": {
        **review["review_metadata"]["candidate_binding"], "artifact_id": "not-a-uuid"}}}
    with pytest.raises(ReviewFindingsUnavailable):
        await run([malformed])


def _submission():
    return FindingDecisionSubmission(
        artifact_id=uuid4(),
        artifact_version=1,
        artifact_hash="a" * 64,
        document_revision_id=uuid4(),
        generation=0,
        fencing_token=0,
        source_item_id="risk-sha256:" + "b" * 64,
        ordinal=0,
        action="CONFIRMED",
        expected_ledger_revision=0,
        idempotency_key="idem-key-0001",
    )


class _UseCase:
    outcome: object = None

    def __init__(self, session):
        pass

    async def execute(self, **_):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raised", "status", "code"),
    [
        (FindingReviewerNotAuthorized("no"), 403, "reviewer_not_authorized"),
        (FindingDecisionIdentityError("no actionable review for tenant"), 404, "review_unavailable"),
        (FindingDecisionIdentityError("missing active tenant-scoped review row"), 404, "review_unavailable"),
        (FindingDecisionIdentityError("pending review was rebound or superseded"), 409, "stale_or_unbound_candidate"),
        (FindingDecisionRevisionConflict("stale ledger revision"), 409, "stale_ledger_revision"),
        (FindingDecisionIdempotencyConflict("replay key has different contents"), 409, "idempotency_conflict"),
    ],
)
async def test_the_decision_route_maps_every_refusal_to_a_stable_code(monkeypatch, raised, status, code) -> None:
    from sqlalchemy.exc import DBAPIError

    monkeypatch.setattr(router, "RecordFindingDecisionUseCase", _UseCase)
    _UseCase.outcome = raised
    user = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), role=UserRole.USER, is_active=True)
    with pytest.raises(HTTPException) as refused:
        await router.record_finding_decision(uuid4(), _submission(), current_user=user, session=object())
    assert (refused.value.status_code, refused.value.detail["code"]) == (status, code)

    _UseCase.outcome = DBAPIError("stmt", {}, Exception("guard"))
    with pytest.raises(HTTPException) as guarded:
        await router.record_finding_decision(uuid4(), _submission(), current_user=user, session=object())
    assert (guarded.value.status_code, guarded.value.detail["code"]) == (409, "ledger_guard_refused")


@pytest.mark.asyncio
async def test_the_decision_route_returns_the_receipt_as_provisional(monkeypatch) -> None:
    monkeypatch.setattr(router, "RecordFindingDecisionUseCase", _UseCase)
    event_id = uuid4()
    _UseCase.outcome = FindingDecisionWriteReceipt(event_id=event_id, ledger_revision=4, replayed=False)
    user = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), role=UserRole.USER, is_active=True)
    receipt = await router.record_finding_decision(uuid4(), _submission(), current_user=user, session=object())
    assert (receipt.event_id, receipt.ledger_revision, receipt.replayed) == (event_id, 4, False)
    assert receipt.decision_scope == "PROVISIONAL_REVIEWER_INTENT"


@pytest.mark.asyncio
async def test_the_list_route_maps_denial_and_absence_and_serializes_the_view(monkeypatch) -> None:
    tenant, user, row_id, review, candidate, identity = _world()

    async def listed(*results, as_user=user):
        class _Svc(ReviewFindingsViewService):
            pass

        monkeypatch.setattr(router, "ReviewFindingsViewService", lambda session: _Svc(_Session(*results)))
        return await router.list_review_findings(row_id, current_user=as_user, session=object())

    body = await listed([review], [candidate], [])
    assert body.final_approval == "SEPARATE_ACT" and len(body.findings) == 2 and body.findings[0].history == []

    with pytest.raises(HTTPException) as absent:
        await listed([])
    assert absent.value.status_code == 404
    viewer = SimpleNamespace(**{**vars(user), "role": UserRole.VIEWER})
    with pytest.raises(HTTPException) as denied:
        await listed(as_user=viewer)
    assert denied.value.status_code == 403
