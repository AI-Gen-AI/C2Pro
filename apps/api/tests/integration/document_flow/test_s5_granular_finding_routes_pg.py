"""ACC-01 S5 (granular HITL): the REAL route handlers over REAL PostgreSQL, finding by finding.

Same world as ``test_s5_hitl_reject_and_differentiated_approval`` (a real ingested contract, a real interrupted
LangGraph, a PROPOSED candidate with two risks bound to the pending review). What is proven here is the HTTP layer
that exposes the already-governed use case:

* the read model lists exactly the candidate's risks with their pins, and the ledger shows what was decided;
* a decision is attributed to the authenticated human, is provisional (the review stays pending, the artifact stays
  PROPOSED) and appends to the ledger; replaying it is idempotent, a contradictory replay is a 409;
* tenant negatives (another tenant's reviewer, a non-human role), stale pins and a stale ledger revision are refused
  with no ledger row left behind;
* once the FINAL approval commits the candidate, no finding can be listed or decided any more.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.modules.hitl.adapters.http.finding_decision_router import (
    list_review_findings,
    record_finding_decision,
)
from src.modules.hitl.domain.finding_decision import FindingDecisionAction
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (  # noqa: F401
    _clean_recovery_discovery_rows,
    real_saver,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    worker,  # noqa: F401
)
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (  # noqa: F401
    _build_graph_with_durable_persistence,
    _ledger,
    _status,
    _submission,
    world,
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    _post_approve,
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


async def _list(w: Any, user: Any, *, tenant_id: Any = None) -> Any:
    async with w.sessions(tenant_id or w.tenant_id) as session:
        return await list_review_findings(w.review_row_id, current_user=user, session=session)


async def _post(w: Any, user: Any, submission: Any, *, tenant_id: Any = None) -> Any:
    async with w.sessions(tenant_id or w.tenant_id) as session:
        receipt = await record_finding_decision(
            w.review_row_id, submission, current_user=user, session=session
        )
        await session.commit()
        return receipt


async def test_the_read_model_lists_the_candidate_risks_with_the_pins_a_decision_must_echo(
    test_user: Any, world: Any
) -> None:
    w = world
    view = await _list(w, test_user)

    assert view.decision_scope == "PROVISIONAL_REVIEWER_INTENT" and view.final_approval == "SEPARATE_ACT"
    assert (view.artifact_id, view.artifact_version, view.artifact_hash) == (
        w.artifact_id,
        w.artifact_version,
        w.artifact_hash,
    )
    assert (view.document_revision_id, view.generation, view.fencing_token) == (
        w.revision_id,
        w.generation,
        w.fencing_token,
    )
    assert view.ledger_revision == 0
    assert [f.ordinal for f in view.findings] == [0, 1]
    assert [f.source_item_id for f in view.findings] == [risk_source_item_id(r) for r in w.risks]
    assert [f.risk["title"] for f in view.findings] == ["Late completion penalty", "Price revision clause"]
    assert all(f.current is None and f.history == [] for f in view.findings)


async def test_a_decision_is_attributed_to_the_human_stays_provisional_and_shows_in_the_read_model(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    first = await _post(w, test_user, _submission(w, ordinal=0, action=FindingDecisionAction.CONFIRMED, expected=0))
    second = await _post(
        w,
        test_user,
        _submission(
            w, ordinal=1, action=FindingDecisionAction.DISMISSED, expected=1, reason="the clause was waived"
        ),
    )
    assert (first.ledger_revision, first.replayed, second.ledger_revision) == (1, False, 2)

    view = await _list(w, test_user)
    assert view.ledger_revision == 2
    assert [f.current.action for f in view.findings if f.current] == ["CONFIRMED", "DISMISSED"]
    assert view.findings[1].current.reason == "the clause was waived"
    assert {f.current.reviewer_id for f in view.findings if f.current} == {str(test_user.id)}

    state = await _status(db, w)
    assert state["review"] == "PENDING_REVIEW_REQUIRED", "a finding decision never approves the review"
    assert [(v, t) for v, t, *_ in state["artifacts"]] == [(1, "proposed")]


async def test_a_later_decision_on_the_same_finding_supersedes_without_erasing_history(
    test_user: Any, world: Any
) -> None:
    w = world
    await _post(w, test_user, _submission(w, ordinal=0, action=FindingDecisionAction.NEEDS_INFO, expected=0, reason="ask legal"))
    await _post(w, test_user, _submission(w, ordinal=0, action=FindingDecisionAction.CONFIRMED, expected=1))

    finding = (await _list(w, test_user)).findings[0]
    assert finding.current.action == "CONFIRMED"
    assert [h.action for h in finding.history] == ["NEEDS_INFO", "CONFIRMED"]


async def test_replay_is_idempotent_and_a_contradictory_replay_or_stale_revision_is_a_409(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    key = f"replay-{uuid4().hex}"
    first = await _post(w, test_user, _submission(w, ordinal=0, key=key))
    again = await _post(w, test_user, _submission(w, ordinal=0, key=key))
    assert again.replayed is True and again.event_id == first.event_id

    with pytest.raises(HTTPException) as changed:
        await _post(w, test_user, _submission(w, ordinal=0, key=key, action=FindingDecisionAction.DISMISSED, reason="x" * 10))
    assert (changed.value.status_code, changed.value.detail["code"]) == (409, "idempotency_conflict")

    with pytest.raises(HTTPException) as stale:
        await _post(w, test_user, _submission(w, ordinal=1, expected=0))
    assert (stale.value.status_code, stale.value.detail["code"]) == (409, "stale_ledger_revision")
    assert len(await _ledger(db, w)) == 1


async def test_pins_of_another_candidate_or_a_foreign_finding_are_refused_and_leave_no_row(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    for override in (
        {"artifact_hash": "0" * 64},
        {"artifact_version": w.artifact_version + 1},
        {"generation": w.generation + 1},
        {"fencing_token": w.fencing_token + 1},
        {"source_item_id": "risk-sha256:" + "f" * 64},
    ):
        with pytest.raises(HTTPException) as refused:
            await _post(w, test_user, _submission(w, ordinal=0, **override))
        assert (refused.value.status_code, refused.value.detail["code"]) == (409, "stale_or_unbound_candidate")
    assert await _ledger(db, w) == []


async def test_another_tenant_and_non_human_roles_cannot_list_or_decide(
    db: AsyncSession, test_user: Any, test_user_2: Any, world: Any
) -> None:
    w = world
    # A reviewer of tenant B inside tenant B does not even find tenant A's review.
    with pytest.raises(HTTPException) as listed:
        await _list(w, test_user_2, tenant_id=test_user_2.tenant_id)
    assert listed.value.status_code == 404
    with pytest.raises(HTTPException) as decided:
        await _post(w, test_user_2, _submission(w, ordinal=0), tenant_id=test_user_2.tenant_id)
    assert decided.value.status_code == 404

    for role in (UserRole.VIEWER, UserRole.API):
        outsider = SimpleNamespace(id=uuid4(), tenant_id=w.tenant_id, is_active=True, role=role)
        with pytest.raises(HTTPException) as denied_list:
            await _list(w, outsider)
        with pytest.raises(HTTPException) as denied_post:
            await _post(w, outsider, _submission(w, ordinal=0))
        assert (denied_list.value.status_code, denied_post.value.status_code) == (403, 403)
    assert await _ledger(db, w) == []


async def test_after_the_final_approval_no_finding_can_be_listed_or_decided(
    db: AsyncSession, test_user: Any, world: Any, request_sessions: Any  # noqa: F811
) -> None:
    w = world
    await _post(w, test_user, _submission(w, ordinal=0, expected=0))

    await _post_approve(
        request_sessions,
        w.tenant_id,
        w.review_item_id,
        saver=w.saver,
        app=w.app,
        sessions=w.sessions,
        row_id=w.review_row_id,
    )

    with pytest.raises(HTTPException) as listed:
        await _list(w, test_user)
    assert listed.value.status_code == 404
    with pytest.raises(HTTPException) as decided:
        await _post(w, test_user, _submission(w, ordinal=1, expected=1))
    assert decided.value.status_code == 404
    assert len(await _ledger(db, w)) == 1, "the ledger keeps what was decided before the approval"
