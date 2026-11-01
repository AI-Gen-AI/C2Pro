"""S5-02 on PostgreSQL: the per-project authority, through the REAL route handlers and the use-case boundary.

Everything below runs against a real review of project P1 (the controlled candidate), explicit rows of
``project_review_grants`` and real ``users`` rows. The tenant is in ``enforce`` unless a test says otherwise.

What is proven (RED before ``ProjectReviewAuthorizer`` existed: every one of these actors was allowed, because being an
active ADMIN/USER of the tenant was the only rule):

* a member with no grant on P1 cannot read, decide or finalize it -- 404, nothing changes, even an ADMIN;
* the three capabilities are independent: READ_REVIEW reads, REVIEW_FINDING decides one finding, APPROVE_CANDIDATE
  finalizes; none implies another; a member with SOME capability but not this one gets 403 (stable code);
* P1 vs P2 inside ONE tenant: a person fully granted on P2 is a stranger to P1;
* revocation is effective on the next request;
* ``audit`` and ``off`` are transitional (would-deny is logged / legacy rule); a missing or unknown mode is ``enforce``;
* the control is at the application boundary (``ResumeWorkflowUseCase.execute``), not only HTTP, and fails closed when
  it cannot even be built;
* the capabilities endpoint reports only the caller's own effective capabilities.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from src.core.auth.models import User, UserRole
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.http import finding_decision_router as findings
from src.modules.hitl.adapters.persistence.project_review_grants import ProjectReviewGrantRepository
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.final_decision_authorization import AuthorizedFinalDecider
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectAuthorizationUnavailable,
    ProjectCapability,
)
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (  # noqa: F401
    _clean_recovery_discovery_rows,
    real_saver,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    worker,  # noqa: F401
)
from tests.integration.document_flow.test_s5_controlled_findings_pg import (  # noqa: F401
    controlled,
    no_risks,
)
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
    _ledger,
    _submission,
    world,  # noqa: F401
)
from tests.integration.document_flow.test_s5_project_authorization_evidence_pg import (
    _final,
    _footprint,
)
from tests.modules.integration.grants_world import apply_grants_schema
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio

READ, FIND, APPROVE = ProjectCapability.READ_REVIEW, ProjectCapability.REVIEW_FINDING, ProjectCapability.APPROVE_CANDIDATE


class Actors:
    """Real ``users`` rows of the tenant plus the means to grant to them (the grantor is a real ADMIN)."""

    def __init__(self, db: AsyncSession, w: Any) -> None:
        self.db, self.w = db, w
        self.admin_id: UUID | None = None

    async def user(self, role: UserRole = UserRole.USER, *, label: str = "u", tenant_id: UUID | None = None) -> Any:
        suffix = uuid4().hex[:8]
        row = User(
            id=uuid4(), tenant_id=tenant_id or self.w.tenant_id, email=f"{label}-{suffix}@example.invalid",
            clerk_user_id=f"clerk_{label}_{suffix}", role=role, is_active=True, is_verified=True,
            first_name=label, last_name="Test",
        )
        self.db.add(row)
        await self.db.commit()
        return SimpleNamespace(
            id=row.id, tenant_id=row.tenant_id, role=role, is_active=True, full_name=f"{label.title()} {role.value.title()}"
        )

    async def admin(self) -> UUID:
        if self.admin_id is None:
            self.admin_id = (await self.user(UserRole.ADMIN, label="grantor")).id
        return self.admin_id

    async def grant(self, who: Any, *caps: ProjectCapability, project: UUID | None = None) -> dict[ProjectCapability, UUID]:
        out: dict[ProjectCapability, UUID] = {}
        for cap in caps:
            out[cap] = await ProjectReviewGrantRepository(self.db).grant(
                tenant_id=self.w.tenant_id, project_id=project or self.w.project_id, user_id=who.id, capability=cap,
                granted_by=await self.admin(), reason=f"test grant {cap.value}",
            )
        await self.db.commit()
        return out

    async def revoke(self, grant_id: UUID) -> None:
        await ProjectReviewGrantRepository(self.db).revoke(
            tenant_id=self.w.tenant_id, grant_id=grant_id, revoked_by=await self.admin(), reason="test revocation"
        )
        await self.db.commit()

    async def mode(self, value: str | None) -> None:
        if value is None:
            sql = "UPDATE tenants SET settings = coalesce(settings, '{}'::jsonb) - 'hitl_project_authorization' WHERE id = :t"
            params: dict[str, Any] = {"t": self.w.tenant_id}
        else:
            sql = (
                "UPDATE tenants SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), '{hitl_project_authorization}', "
                "cast(:v as jsonb), true) WHERE id = :t"
            )
            params = {"t": self.w.tenant_id, "v": f'{{"mode": "{value}"}}'}
        await self.db.execute(text(sql), params)
        await self.db.commit()

    async def other_project(self) -> UUID:
        project = uuid4()
        await self.db.execute(
            text(
                "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
                "VALUES (:id, :t, 'P2', :code, 'construction', 'active', 'EUR', now(), now())"
            ),
            {"id": project, "t": self.w.tenant_id, "code": f"p2-{project.hex[:6]}"},
        )
        await self.db.commit()
        return project


@pytest.fixture
async def actors(db: AsyncSession, controlled: Any) -> Actors:
    a = Actors(db, controlled)
    await apply_grants_schema(db)  # the table is not in the ORM metadata (like the finding ledger)
    await a.mode("enforce")
    return a


async def _read(w: Any, user: Any) -> Any:
    async with w.sessions(w.tenant_id) as session:
        return await findings.list_review_findings(w.review_row_id, current_user=user, session=session)


async def _decide(w: Any, user: Any, **kw: Any) -> Any:
    async with w.sessions(w.tenant_id) as session:
        receipt = await findings.record_finding_decision(
            w.review_row_id, _submission(w, **kw), current_user=user, session=session
        )
        await session.commit()
        return receipt


async def _caps(w: Any, user: Any) -> Any:
    async with w.sessions(w.tenant_id) as session:
        return await findings.get_review_capabilities(w.review_row_id, current_user=user, session=session)


def _code(exc: HTTPException) -> str:
    return exc.detail["code"] if isinstance(exc.detail, dict) else str(exc.detail)


async def _refused(call: Any) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        await call
    return caught.value


# ── no grant, no authority ─────────────────────────────────────────────────────────────────────────────────────
async def test_in_enforce_a_member_without_any_grant_on_the_project_cannot_read_decide_or_finalize_even_an_admin(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    before = await _footprint(db, w)
    for role in (UserRole.USER, UserRole.ADMIN):
        stranger = await actors.user(role, label="stranger")
        for name, call in (
            ("read", _read(w, stranger)),
            ("decide", _decide(w, stranger, ordinal=0, expected=0)),
            ("capabilities", _caps(w, stranger)),
            ("approve", _final(w, request_sessions, "approve", stranger)),
            ("reject", _final(w, request_sessions, "reject", stranger)),
            ("resume", _final(w, request_sessions, "resume", stranger)),
        ):
            refusal = await _refused(call)
            assert (refusal.status_code, _code(refusal)) == (404, "review_unavailable"), (role, name)
    assert await _ledger(db, w) == []
    assert await _footprint(db, w) == before, "nothing changed: no decision, no TRUSTED, no event"


# ── the three capabilities are independent ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("held", "can_read", "can_decide", "can_approve"),
    [
        ((READ,), True, False, False),
        ((FIND,), False, True, False),
        ((APPROVE,), False, False, True),
        ((READ, FIND), True, True, False),
        ((READ, APPROVE), True, False, True),
        ((FIND, APPROVE), False, True, True),
    ],
    ids=["read", "review", "approve", "read+review", "read+approve", "review+approve"],
)
async def test_each_capability_authorizes_only_its_own_act_and_a_partial_holder_gets_403_with_a_stable_code(
    db: AsyncSession, actors: Actors, request_sessions: Any,  # noqa: F811
    held: tuple[ProjectCapability, ...], can_read: bool, can_decide: bool, can_approve: bool,
) -> None:
    w = actors.w
    person = await actors.user(label="partial")
    await actors.grant(person, *held)
    if can_read:
        assert len((await _read(w, person)).findings) == 5
    else:
        refusal = await _refused(_read(w, person))
        assert (refusal.status_code, _code(refusal)) == (403, "project_capability_required")
    if can_decide:
        receipt = await _decide(w, person, ordinal=0, expected=0)
        assert receipt.ledger_revision == 1 and not receipt.replayed
    else:
        refusal = await _refused(_decide(w, person, ordinal=1, expected=0))
        assert (refusal.status_code, _code(refusal)) == (403, "project_capability_required")
        assert "REVIEW_FINDING" in refusal.detail["message"]
    if not can_approve:
        before = await _footprint(db, w)
        for route in ("approve", "reject", "resume"):
            refusal = await _refused(_final(w, request_sessions, route, person))
            assert (refusal.status_code, _code(refusal)) == (403, "project_capability_required"), route
        assert await _footprint(db, w) == before, "a partial holder changed nothing"
    # a decision recorded above is PROVISIONAL: it never trusted the candidate
    assert (await _footprint(db, w))["review"] == "PENDING_REVIEW_REQUIRED"


async def test_a_person_with_all_three_capabilities_finalizes_and_the_candidate_becomes_trusted(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="full")
    await actors.grant(person, READ, FIND, APPROVE)
    assert len((await _read(w, person)).findings) == 5
    for ordinal in range(5):  # S5-04: under enforce every finding needs a decision before the approval
        await _decide(w, person, ordinal=ordinal, expected=ordinal)
    await _final(w, request_sessions, "approve", person)
    after = await _footprint(db, w)
    assert after["review"] == "APPROVED"
    assert [t for _, t, *_ in after["artifacts"]].count("trusted") == 1


async def test_an_admin_of_the_tenant_without_approve_candidate_cannot_sign_even_with_the_other_two(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    admin = await actors.user(UserRole.ADMIN, label="tenantadmin")
    await actors.grant(admin, READ, FIND)
    before = await _footprint(db, w)
    refusal = await _refused(_final(w, request_sessions, "approve", admin))
    assert (refusal.status_code, _code(refusal)) == (403, "project_capability_required")
    assert await _footprint(db, w) == before


# ── P1 vs P2 inside one tenant ───────────────────────────────────────────────────────────────────────────────
async def test_a_person_fully_granted_on_p2_is_a_stranger_to_the_review_of_p1_in_the_same_tenant(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    p2 = await actors.other_project()
    p1_person, p2_person = await actors.user(label="p1"), await actors.user(label="p2")
    await actors.grant(p1_person, READ, FIND, APPROVE)
    await actors.grant(p2_person, READ, FIND, APPROVE, project=p2)
    before = await _footprint(db, w)

    for call in (
        _read(w, p2_person), _decide(w, p2_person, ordinal=0, expected=0), _caps(w, p2_person),
        _final(w, request_sessions, "approve", p2_person), _final(w, request_sessions, "reject", p2_person),
        _final(w, request_sessions, "resume", p2_person),
    ):
        refusal = await _refused(call)
        assert (refusal.status_code, _code(refusal)) == (404, "review_unavailable")
    assert await _footprint(db, w) == before and await _ledger(db, w) == []
    # and the P1 person is unaffected
    assert len((await _read(w, p1_person)).findings) == 5


# ── revocation ───────────────────────────────────────────────────────────────────────────────────────────────
async def test_revoking_a_capability_takes_effect_on_the_next_request_and_leaves_the_others(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="revoked")
    grants = await actors.grant(person, READ, APPROVE)
    assert len((await _read(w, person)).findings) == 5
    await actors.revoke(grants[APPROVE])
    refusal = await _refused(_final(w, request_sessions, "approve", person))
    assert (refusal.status_code, _code(refusal)) == (403, "project_capability_required")
    assert (await _footprint(db, w))["review"] == "PENDING_REVIEW_REQUIRED"
    assert len((await _read(w, person)).findings) == 5, "READ_REVIEW was not revoked"
    await actors.revoke(grants[READ])
    refusal = await _refused(_read(w, person))
    assert (refusal.status_code, _code(refusal)) == (404, "review_unavailable"), "no grant left: the review disappears"


async def test_a_grant_of_a_deactivated_member_is_dead_even_if_the_token_still_says_active(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="deactivated")
    await actors.grant(person, READ, FIND, APPROVE)
    await db.execute(text("UPDATE users SET is_active = false WHERE id = :u"), {"u": person.id})
    await db.commit()
    for call in (_read(w, person), _final(w, request_sessions, "approve", person)):
        assert (await _refused(call)).status_code == 404
    assert (await _footprint(db, w))["review"] == "PENDING_REVIEW_REQUIRED"


# ── modes ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_audit_logs_would_deny_and_allows_off_is_the_legacy_rule_and_both_are_labelled_transitional(
    actors: Actors,
) -> None:
    w = actors.w
    stranger = await actors.user(label="legacy")
    await actors.mode("audit")
    with capture_logs() as logs:
        assert len((await _read(w, stranger)).findings) == 5
    would_deny = [e for e in logs if e["event"] == "hitl_project_authorization_would_deny"]
    assert would_deny and would_deny[0]["capability"] == "READ_REVIEW" and would_deny[0]["user_id"] == str(stranger.id)
    caps = await _caps(w, stranger)
    assert caps.mode == "audit" and (caps.read_review, caps.review_finding, caps.approve_candidate) == (True, True, True)

    await actors.mode("off")
    with capture_logs() as logs:
        assert len((await _read(w, stranger)).findings) == 5
    assert not [e for e in logs if "would_deny" in e["event"]]
    assert (await _caps(w, stranger)).mode == "off"


@pytest.mark.parametrize("value", [None, "banana", ""], ids=["missing", "unknown", "empty"])
async def test_a_missing_or_unknown_mode_is_enforce_never_a_silent_off(actors: Actors, value: str | None) -> None:
    await actors.mode(value)
    stranger = await actors.user(label="failclosed")
    refusal = await _refused(_read(actors.w, stranger))
    assert refusal.status_code == 404


# ── the application boundary, not only HTTP ──────────────────────────────────────────────────────────────────
async def test_the_use_case_itself_refuses_an_ungranted_decider_and_fails_closed_without_a_session(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    stranger = await actors.user(label="boundary")
    decider = AuthorizedFinalDecider(tenant_id=w.tenant_id, user_id=stranger.id, display_name="Boundary Stranger")
    before = await _footprint(db, w)
    async with request_sessions() as session:
        await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(w.tenant_id)})
        repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=w.tenant_id)
        use_case = ResumeWorkflowUseCase(
            review_queue_repo=repo, checkpoint_service=CheckpointService(checkpointer=w.saver), graph_app=w.app,
            claim_session_factory=w.sessions,
        )
        for decision in (WorkflowDecision.APPROVE, WorkflowDecision.REJECT):
            with pytest.raises(ProjectAuthorizationDenied) as caught:
                await use_case.execute(
                    w.review_row_id, ResumeWorkflowRequest(decision=decision, feedback="x", approved_by="x", decider=decider)
                )
            assert caught.value.capability is APPROVE and caught.value.visible is False

    class _NoSession:
        async def get_review_item(self, _id: UUID) -> Any:
            return SimpleNamespace(metadata={"project_id": str(w.project_id)}, current_status=None)

    with pytest.raises(ProjectAuthorizationUnavailable):
        await ResumeWorkflowUseCase(review_queue_repo=_NoSession()).execute(  # type: ignore[arg-type]
            w.review_row_id,
            ResumeWorkflowRequest(decision=WorkflowDecision.APPROVE, feedback="x", approved_by="x", decider=decider),
        )
    assert await _footprint(db, w) == before


async def test_the_non_graph_decision_path_applies_the_same_authority(db: AsyncSession, actors: Actors) -> None:
    from src.modules.hitl.adapters.http import router as hitl_router

    w = actors.w
    stranger = await actors.user(label="legacypath")
    decider = AuthorizedFinalDecider(tenant_id=w.tenant_id, user_id=stranger.id, display_name="x")
    row = SimpleNamespace(metadata={"project_id": str(w.project_id)})
    async with w.sessions(w.tenant_id) as session:
        service = SimpleNamespace(review_queue_repo=SqlAlchemyReviewQueueRepository(session=session, tenant_id=w.tenant_id))
        refusal = await _refused(hitl_router._require_project_approval_for_legacy_row(service, row, decider))
        assert refusal.status_code == 404
        await actors.grant(stranger, READ)
        refusal = await _refused(hitl_router._require_project_approval_for_legacy_row(service, row, decider))
        assert refusal.status_code == 403
        await actors.grant(stranger, APPROVE)
        await hitl_router._require_project_approval_for_legacy_row(service, row, decider)  # allowed now
        # a row without any project cannot be authorized in enforce
        refusal = await _refused(hitl_router._require_project_approval_for_legacy_row(service, SimpleNamespace(metadata={}), decider))
        assert refusal.status_code == 404


# ── the capabilities endpoint ────────────────────────────────────────────────────────────────────────────────
async def test_capabilities_report_only_the_callers_own_effective_capabilities(actors: Actors) -> None:
    w = actors.w
    mine, theirs = await actors.user(label="mine"), await actors.user(label="theirs")
    await actors.grant(mine, READ, FIND)
    await actors.grant(theirs, READ, FIND, APPROVE)
    caps = await _caps(w, mine)
    assert (caps.mode, caps.read_review, caps.review_finding, caps.approve_candidate) == ("enforce", True, True, False)
    assert set(findings.ReviewCapabilitiesResponse.model_fields) == {
        "review_row_id", "mode", "read_review", "review_finding", "approve_candidate",
    }, "no grant ids, no names, nothing about other people"
    assert (await _caps(w, theirs)).approve_candidate is True


async def test_the_findings_read_carries_the_callers_own_capabilities_so_the_screen_needs_no_extra_request(
    actors: Actors,
) -> None:
    w = actors.w
    reader = await actors.user(label="readonly")
    await actors.grant(reader, READ)
    view = await _read(w, reader)
    assert view.capabilities is not None
    assert (view.capabilities.mode, view.capabilities.read_review) == ("enforce", True)
    assert (view.capabilities.review_finding, view.capabilities.approve_candidate) == (False, False)
    full = await actors.user(label="fullcaps")
    await actors.grant(full, READ, FIND, APPROVE)
    caps = (await _read(w, full)).capabilities
    assert caps is not None and (caps.review_finding, caps.approve_candidate) == (True, True)
