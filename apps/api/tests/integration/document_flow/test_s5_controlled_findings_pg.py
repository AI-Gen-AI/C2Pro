"""ACC-01 S5 with a CONTROLLED candidate: five KNOWN RISK findings, four actions, decided finding by finding.

NOT a UAT with real AI. The deterministic provider extracts no risks, so the candidate is replaced -- through the
product's own governed ``propose_correction`` (see ``scripts.seed_controlled_s5_findings``) -- by one that carries five
authored risks, bound to the SAME pending review (thread, checkpoint, generation, fencing token) and to its new
artifact id / version / SHA-256. Everything else is the real thing: a real ingested contract, a real interrupted
LangGraph, the real route handlers and real PostgreSQL.

Proven: the read model lists exactly the authored risks with the pins of the new candidate; CONFIRMED, DISMISSED,
NEEDS_INFO and CORRECTION_PROPOSED are each persisted, attributed to the authenticated human and visible; replay is
idempotent; stale pins (including the superseded Vn), a stale ledger revision and a foreign tenant are refused with no
row left behind; and the separate FINAL approval trusts exactly the decided candidate, unchanged by the decisions.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_controlled_s5_findings import (
    CONTROLLED_RISKS,
    ControlledSeedError,
    require_nonproduction,
    seed_controlled_findings,
)
from src.core.auth.dependencies import get_current_user
from src.modules.hitl.adapters.http import finding_decision_router as routes
from src.modules.hitl.domain.finding_decision import FindingDecisionAction
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id
from tests.integration.document_flow import test_s5_hitl_reject_and_differentiated_approval as s5
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (  # noqa: F401
    _clean_recovery_discovery_rows,
    real_saver,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    worker,  # noqa: F401
)
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
    _ledger,
    _status,
    _submission,
    world,  # noqa: F401  (pytest fixture)
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    _post_approve,
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def no_risks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deterministic provider extracts none: the shared world builds its candidate without findings."""
    monkeypatch.setattr(s5, "RISKS", [])


@pytest.fixture
async def controlled(no_risks: None, world: Any, db: AsyncSession) -> Any:  # noqa: ARG001
    """The world exactly as the deterministic provider leaves it (a candidate with NO risks), then the seed."""
    w = world
    assert w.risks == [], "the deterministic candidate extracts no findings"
    first = {"artifact_id": w.artifact_id, "artifact_hash": w.artifact_hash, "artifact_version": w.artifact_version}

    async with w.sessions(w.tenant_id) as session:
        report = await seed_controlled_findings(session, tenant_id=w.tenant_id, document_id=w.document_id)
        await session.commit()

    await db.commit()
    artifact = (
        await db.execute(
            text(
                "SELECT artifact_id, artifact_version, artifact_hash, payload FROM document_artifacts "
                "WHERE document_id = :d AND trust_state = 'proposed'"
            ),
            {"d": w.document_id},
        )
    ).one()
    import json

    payload = artifact.payload if isinstance(artifact.payload, dict) else json.loads(artifact.payload)
    w.superseded = first
    w.report = report
    w.artifact_id, w.artifact_version, w.artifact_hash = artifact.artifact_id, artifact.artifact_version, artifact.artifact_hash
    w.risks = payload["extracted_risks"]
    return w


async def _list(w: Any, user: Any, *, tenant_id: Any = None) -> Any:
    async with w.sessions(tenant_id or w.tenant_id) as session:
        return await routes.list_review_findings(w.review_row_id, current_user=user, session=session)


async def _post(w: Any, user: Any, submission: Any, *, tenant_id: Any = None) -> Any:
    async with w.sessions(tenant_id or w.tenant_id) as session:
        receipt = await routes.record_finding_decision(w.review_row_id, submission, current_user=user, session=session)
        await session.commit()
        return receipt


async def test_the_seed_replaces_the_candidate_by_the_governed_correction_and_keeps_the_review(
    db: AsyncSession, controlled: Any
) -> None:
    w = controlled
    state = await _status(db, w)
    assert state["review"] == "PENDING_REVIEW_REQUIRED" and str(w.review_row_id) == w.report["review_row_id"]
    by_version = {v: (t, h) for v, t, _, h in state["artifacts"]}
    assert by_version[w.artifact_version][0] == "proposed" and by_version[w.artifact_version][1] == w.artifact_hash
    assert all(t != "trusted" for t, _ in by_version.values()), "the seed trusts nothing"
    assert w.report["artifact_hash"] == w.artifact_hash and w.report["evidence_class"] == "DETERMINISTIC_CONTROLLED_CANDIDATE"
    assert w.artifact_hash != w.superseded["artifact_hash"], "a different, exactly bound candidate"
    binding = state["metadata"]["candidate_binding"]
    assert (binding["artifact_id"], binding["artifact_hash"]) == (str(w.artifact_id), w.artifact_hash)


async def test_the_read_model_lists_the_five_authored_risks_with_the_pins_of_the_new_candidate(
    test_user: Any, controlled: Any
) -> None:
    w = controlled
    view = await _list(w, test_user)
    assert (view.artifact_id, view.artifact_version, view.artifact_hash) == (w.artifact_id, w.artifact_version, w.artifact_hash)
    assert (view.document_revision_id, view.generation, view.fencing_token) == (w.revision_id, w.generation, w.fencing_token)
    assert [f.risk["title"] for f in view.findings] == [r["title"] for r in CONTROLLED_RISKS]
    assert [f.risk["clause_ref"] for f in view.findings] == ["Clause 14.2", "Clause 9.4", "Clause 21.1", "Clause 6.3", "Clause 4.1"]
    assert [f.risk["severity"] for f in view.findings] == ["HIGH", "MEDIUM", "CRITICAL", "MEDIUM", "LOW"]
    assert [f.source_item_id for f in view.findings] == [risk_source_item_id(r) for r in w.risks]
    assert view.ledger_revision == 0 and all(f.current is None for f in view.findings)


async def test_the_four_actions_are_persisted_attributed_visible_and_decide_nothing(
    db: AsyncSession, test_user: Any, controlled: Any
) -> None:
    w = controlled
    before = await _status(db, w)
    plan = [
        (0, FindingDecisionAction.CONFIRMED, None, None),
        (1, FindingDecisionAction.DISMISSED, "Superseded by change order 7.", None),
        (2, FindingDecisionAction.NEEDS_INFO, "Ask legal whether the cap exists in the annex.", None),
        (3, FindingDecisionAction.CORRECTION_PROPOSED, "The deemed approval period is 14 days.", "Silence for 14 days is deemed approval."),
    ]
    for expected, (ordinal, action, reason, text_) in enumerate(plan):
        receipt = await _post(
            w,
            test_user,
            _submission(w, ordinal=ordinal, action=action, expected=expected, reason=reason, proposed_text=text_),
        )
        assert (receipt.ledger_revision, receipt.replayed) == (expected + 1, False)
        assert receipt.decision_scope == "PROVISIONAL_REVIEWER_INTENT"

    rows = await _ledger(db, w)
    assert [(r.ledger_revision, r.action) for r in rows] == [(1, "CONFIRMED"), (2, "DISMISSED"), (3, "NEEDS_INFO"), (4, "CORRECTION_PROPOSED")]
    assert {r.reviewer_id for r in rows} == {str(test_user.id)}, "the decider is the authenticated human, never client data"
    assert len({r.finding_id for r in rows}) == 4

    view = await _list(w, test_user)
    assert view.ledger_revision == 4
    assert [f.current.action if f.current else None for f in view.findings] == [
        "CONFIRMED", "DISMISSED", "NEEDS_INFO", "CORRECTION_PROPOSED", None,
    ]
    assert view.findings[3].current.proposed_text == "Silence for 14 days is deemed approval."
    assert view.findings[1].current.reason == "Superseded by change order 7."

    after = await _status(db, w)
    assert after["review"] == "PENDING_REVIEW_REQUIRED" and after["artifacts"] == before["artifacts"], (
        "four provisional decisions changed neither the review nor the candidate (same hash, still PROPOSED)"
    )


async def test_replay_is_idempotent_and_every_conflict_is_refused_without_a_row(
    db: AsyncSession, test_user: Any, test_user_2: Any, controlled: Any
) -> None:
    w = controlled
    key = f"replay-{uuid4().hex}"
    first = await _post(w, test_user, _submission(w, ordinal=0, key=key))
    again = await _post(w, test_user, _submission(w, ordinal=0, key=key))
    assert again.replayed is True and again.event_id == first.event_id

    def refused(coro: Any, code: str):  # noqa: ANN202
        async def run() -> None:
            with pytest.raises(HTTPException) as caught:
                await coro
            assert (caught.value.status_code, caught.value.detail["code"]) == (409, code)

        return run()

    await refused(_post(w, test_user, _submission(w, ordinal=0, key=key, action=FindingDecisionAction.DISMISSED, reason="changed my mind")), "idempotency_conflict")
    await refused(_post(w, test_user, _submission(w, ordinal=1, expected=0)), "stale_ledger_revision")
    # A decision built against the SUPERSEDED candidate Vn (before the controlled replacement) is stale.
    await refused(
        _post(w, test_user, _submission(w, ordinal=1, expected=1, artifact_id=w.superseded["artifact_id"], artifact_hash=w.superseded["artifact_hash"], artifact_version=w.superseded["artifact_version"])),
        "stale_or_unbound_candidate",
    )
    for override in ({"generation": w.generation + 1}, {"fencing_token": w.fencing_token + 1}, {"source_item_id": "risk-sha256:" + "e" * 64}):
        await refused(_post(w, test_user, _submission(w, ordinal=1, expected=1, **override)), "stale_or_unbound_candidate")
    assert len(await _ledger(db, w)) == 1

    # Another tenant's reviewer neither sees nor decides this review; a non-human role is denied.
    with pytest.raises(HTTPException) as foreign:
        await _list(w, test_user_2, tenant_id=test_user_2.tenant_id)
    assert foreign.value.status_code == 404
    with pytest.raises(HTTPException) as foreign_post:
        await _post(w, test_user_2, _submission(w, ordinal=1, expected=1), tenant_id=test_user_2.tenant_id)
    assert foreign_post.value.status_code == 404
    from src.core.auth.models import UserRole

    viewer = SimpleNamespace(id=uuid4(), tenant_id=w.tenant_id, is_active=True, role=UserRole.VIEWER)
    with pytest.raises(HTTPException) as denied:
        await _post(w, viewer, _submission(w, ordinal=1, expected=1))
    assert denied.value.status_code == 403
    assert len(await _ledger(db, w)) == 1


async def test_the_full_http_layer_serialises_the_same_contract_the_screen_consumes(
    test_user: Any, controlled: Any
) -> None:
    w = controlled
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: test_user

    async def session_dependency():  # noqa: ANN202
        async with w.sessions(w.tenant_id) as session:
            yield session
            await session.commit()

    app.dependency_overrides[routes.get_finding_session] = session_dependency
    base = f"/api/v1/hitl/reviews/{w.review_row_id}/findings"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = (await client.get(base)).json()
        assert listed["decision_scope"] == "PROVISIONAL_REVIEWER_INTENT" and listed["final_approval"] == "SEPARATE_ACT"
        assert len(listed["findings"]) == 5 and listed["findings"][2]["risk"]["severity"] == "CRITICAL"
        body = {
            "artifact_id": listed["artifact_id"], "artifact_version": listed["artifact_version"],
            "artifact_hash": listed["artifact_hash"], "document_revision_id": listed["document_revision_id"],
            "generation": listed["generation"], "fencing_token": listed["fencing_token"],
            "source_item_id": listed["findings"][4]["source_item_id"], "ordinal": 4, "action": "NEEDS_INFO",
            "expected_ledger_revision": listed["ledger_revision"], "idempotency_key": f"http-{uuid4().hex}",
            "reason": "Request the access date from the owner.",
        }
        created = await client.post(f"{base}/decisions", json=body)
        assert created.status_code == 201 and created.json()["ledger_revision"] == 1
        smuggled = await client.post(f"{base}/decisions", json={**body, "idempotency_key": f"http-{uuid4().hex}", "reviewer_id": "someone-else"})
        assert smuggled.status_code == 422, "a client-supplied actor is rejected, never trusted"
        stale = await client.post(f"{base}/decisions", json={**body, "idempotency_key": f"http-{uuid4().hex}"})
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_ledger_revision"
        after = (await client.get(base)).json()
        assert after["findings"][4]["current"]["action"] == "NEEDS_INFO" and after["ledger_revision"] == 1


async def test_the_final_approval_is_the_separate_act_and_trusts_exactly_the_decided_unchanged_candidate(
    db: AsyncSession, test_user: Any, controlled: Any, request_sessions: Any  # noqa: F811
) -> None:
    w = controlled
    await _post(w, test_user, _submission(w, ordinal=0, expected=0))
    await _post(w, test_user, _submission(w, ordinal=1, action=FindingDecisionAction.DISMISSED, expected=1, reason="not applicable"))

    response = await _post_approve(
        request_sessions, w.tenant_id, w.review_item_id, saver=w.saver, app=w.app, sessions=w.sessions, row_id=w.review_row_id,
    )
    assert response.current_status.value == "APPROVED"

    after = await _status(db, w)
    trusted = [(v, h) for v, t, _, h in after["artifacts"] if t == "trusted"]
    assert trusted == [(w.artifact_version, w.artifact_hash)], "exactly the candidate that was decided on became trusted"
    assert all(h != w.superseded["artifact_hash"] for _, h in trusted), "the superseded Vn never became trusted"
    payload = (
        await db.execute(text("SELECT payload FROM document_artifacts WHERE artifact_id = :a"), {"a": w.artifact_id})
    ).scalar_one()
    risks = payload["extracted_risks"] if isinstance(payload, dict) else __import__("json").loads(payload)["extracted_risks"]
    assert [r["title"] for r in risks] == [r["title"] for r in CONTROLLED_RISKS], (
        "CURRENT behaviour, stated so the open architecture decision is explicit: a DISMISSED finding is still part of "
        "the trusted payload -- decisions are provisional and the approval does not read them"
    )
    assert len(await _ledger(db, w)) == 2

    with pytest.raises(HTTPException) as listed:
        await _list(w, test_user)
    assert listed.value.status_code == 404
    with pytest.raises(HTTPException) as late:
        await _post(w, test_user, _submission(w, ordinal=2, expected=2))
    assert late.value.status_code == 404


async def test_the_seed_refuses_what_it_must_not_touch(db: AsyncSession, test_user: Any, controlled: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    w = controlled
    await _post(w, test_user, _submission(w, ordinal=0, expected=0))
    async with w.sessions(w.tenant_id) as session:
        with pytest.raises(ControlledSeedError, match="already has finding decisions"):
            await seed_controlled_findings(session, tenant_id=w.tenant_id, document_id=w.document_id)
        with pytest.raises(ControlledSeedError, match="exactly one pending"):
            await seed_controlled_findings(session, tenant_id=w.tenant_id, document_id=uuid4())
    for name, value in (("ENVIRONMENT", "production"), ("C2PRO_AI_MOCK", "0")):
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
        monkeypatch.setenv(name, value)
        with pytest.raises(ControlledSeedError, match="nonproduction only"):
            require_nonproduction()
