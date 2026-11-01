"""S5 security evidence (PQ-HITL-04C5 / #980): WHAT the product authorizes today, per project and per action.

These are CHARACTERIZATION tests, not a policy. They pin, with the real route handlers over real PostgreSQL, the rules
that exist and the ones that do not, so a missing control is a reproducible fact instead of an assumption:

* the application has NO project-level authorization model: no membership / ACL / assignment table links a user to a
  project (the only table with both a project and a user column is ``disclaimer_acceptances``), and every RLS policy
  on the review ledger is tenant-only. "Two users of one tenant with different permissions on two projects" cannot be
  expressed, so there is nothing the product could deny them with;
* READING findings and RECORDING a provisional decision require an active human ADMIN/USER of the review's TENANT;
* the FINAL approval route (``/hitl/queue/{id}/approve``) requires only an authenticated user of the tenant: it checks
  NO role at all, so a VIEWER reaches the same decision (this is the existing, broader exposure, not new in S5).

When the owner ratifies an authorization policy these tests are the ones to flip: until then they document the gap.
Nothing here widens a permission, invents a role or adds a policy.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.http import finding_decision_router as findings
from src.modules.hitl.adapters.http import router as hitl_router
from src.modules.hitl.adapters.http.schemas import ApproveRequest
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
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
    _status,
    _submission,
    world,  # noqa: F401
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


def _member(tenant_id: UUID, role: UserRole, name: str) -> Any:
    """What ``get_current_user`` yields for an authenticated, active member of the tenant."""
    return SimpleNamespace(id=uuid4(), tenant_id=tenant_id, role=role, is_active=True, full_name=name)


async def _list(w: Any, user: Any) -> Any:
    async with w.sessions(w.tenant_id) as session:
        return await findings.list_review_findings(w.review_row_id, current_user=user, session=session)


async def _decide(w: Any, user: Any, submission: Any) -> Any:
    async with w.sessions(w.tenant_id) as session:
        receipt = await findings.record_finding_decision(w.review_row_id, submission, current_user=user, session=session)
        await session.commit()
        return receipt


async def test_the_application_has_no_project_level_authorization_model(db: AsyncSession) -> None:
    """Static fact about the schema the routes could consult: nothing links a user to a project."""
    from src.core.database import Base
    from src.main import create_application

    create_application()  # registers every ORM model on the metadata
    user_columns = {"user_id", "member_id", "assigned_to", "assignee", "assignee_id", "owner_id"}
    linking = sorted(
        name for name, table in Base.metadata.tables.items()
        if "project_id" in table.columns and user_columns & {c.name for c in table.columns}
    )
    assert linking == ["disclaimer_acceptances"], linking
    assert not [n for n in Base.metadata.tables if any(k in n for k in ("member", "acl", "permission", "grant"))]


async def test_the_ledger_policies_are_tenant_only_not_project_scoped(db: AsyncSession, controlled: Any) -> None:  # noqa: ARG001
    rows = (
        await db.execute(
            text(
                "SELECT tablename, policyname, coalesce(qual, '') || ' ' || coalesce(with_check, '') AS rule "
                "FROM pg_policies WHERE tablename IN ('hitl_finding_decisions', 'review_items')"
            )
        )
    ).all()
    assert rows, "RLS policies exist on the review tables"
    for table, policy, rule in rows:
        assert "app.current_tenant" in rule, (table, policy)
        assert "project" not in rule.lower(), f"{table}.{policy} unexpectedly scopes by project: {rule}"


async def test_any_active_admin_or_user_of_the_tenant_can_read_and_record_whatever_the_project(
    db: AsyncSession, controlled: Any
) -> None:
    """GAP evidence: a member who has nothing to do with the review's project is NOT denied (no project model exists)."""
    w = controlled
    unrelated_admin = _member(w.tenant_id, UserRole.ADMIN, "Admin without any tie to this project")
    unrelated_user = _member(w.tenant_id, UserRole.USER, "User without any tie to this project")

    assert len((await _list(w, unrelated_admin)).findings) == 5
    assert len((await _list(w, unrelated_user)).findings) == 5
    first = await _decide(w, unrelated_user, _submission(w, ordinal=0, expected=0))
    second = await _decide(w, unrelated_admin, _submission(w, ordinal=1, expected=1, action=_dismissed(), reason="no tie"))
    assert (first.ledger_revision, second.ledger_revision) == (1, 2)
    rows = await _ledger(db, w)
    assert {r.reviewer_id for r in rows} == {str(unrelated_user.id), str(unrelated_admin.id)}, (
        "recorded, attributed to the authenticated caller -- and allowed without any project relationship"
    )


def _dismissed() -> Any:
    from src.modules.hitl.domain.finding_decision import FindingDecisionAction

    return FindingDecisionAction.DISMISSED


async def test_findings_routes_deny_non_human_roles_and_inactive_members_which_is_the_only_role_gate(
    db: AsyncSession, controlled: Any
) -> None:
    from fastapi import HTTPException

    w = controlled
    for role in (UserRole.VIEWER, UserRole.API):
        denied = _member(w.tenant_id, role, "non human")
        for call in (_list(w, denied), _decide(w, denied, _submission(w, ordinal=0, expected=0))):
            with pytest.raises(HTTPException) as caught:
                await call
            assert caught.value.status_code == 403
    inactive = _member(w.tenant_id, UserRole.USER, "inactive")
    inactive.is_active = False
    with pytest.raises(HTTPException) as caught:
        await _list(w, inactive)
    assert caught.value.status_code == 403
    assert await _ledger(db, w) == []


async def test_the_final_approval_route_checks_no_role_so_a_viewer_reaches_the_same_decision(
    db: AsyncSession, controlled: Any, request_sessions: Any  # noqa: F811
) -> None:
    """GAP evidence (pre-existing, broader than S5): ``approve_item`` takes any authenticated user of the tenant."""
    w = controlled
    viewer = _member(w.tenant_id, UserRole.VIEWER, "Read-only viewer")
    async with request_sessions() as session:
        await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(w.tenant_id)})
        repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=w.tenant_id)
        use_case = ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=CheckpointService(checkpointer=w.saver),
            graph_app=w.app,
            claim_session_factory=w.sessions,
        )
        try:
            response = await hitl_router.approve_item(
                item_id=w.review_item_id,
                payload=ApproveRequest(row_id=w.review_row_id),
                _tenant_id=w.tenant_id,
                current_user=viewer,
                service=SimpleNamespace(review_queue_repo=repo),
                resume_use_case=use_case,
            )
        finally:
            await session.commit()
    assert response.current_status.value == "APPROVED", "a VIEWER approved: the route has no role gate"
    state = await _status(db, w)
    assert [t for _, t, *_ in state["artifacts"] if t == "trusted"] == ["trusted"]
