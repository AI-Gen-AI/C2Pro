"""SEC-04: real HTTP POST + private PostgreSQL, no mock analysis risk and no production decisions.

The isolated S5 fixture persists the genuine empty extracted_risks candidate via the
product's document_artifact repository; never rewrites a production artifact or
candidate_binding. The HTTP request enters the real HITL router. Authentication and
request-bound sessions are fixture-injected; authorizer, reconciler, ledger and PG are real.
These tests do NOT assert that a production Clerk JWT was used.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import UserRole
from src.core.security import get_current_tenant_id
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.http import router as hitl_router
from src.modules.hitl.adapters.http.dependencies import get_hitl_service, get_resume_workflow_use_case
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (  # noqa: F401
    _clean_recovery_discovery_rows,
    real_saver,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    worker,  # noqa: F401
)
from tests.integration.document_flow.test_s5_controlled_findings_pg import no_risks  # noqa: F401
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
    _ledger,
    world,  # noqa: F401
)
from tests.integration.document_flow.test_s5_project_authorization_evidence_pg import (
    _final,
    _footprint,
)
from tests.integration.document_flow.test_s5_project_review_authorization_pg import (
    APPROVE,
    FIND,
    READ,
    Actors,
)
from tests.modules.integration.grants_world import apply_grants_schema
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def empty_actors(db: AsyncSession, no_risks: None, world: Any) -> Actors:  # noqa: ARG001
    """The real document-analysis journey produces a PROPOSED candidate with 0 N4 risks."""
    assert world.risks == [], "no synthetic findings, and no SQL candidate patching"
    await apply_grants_schema(db)
    actors = Actors(db, world)
    await actors.mode("enforce")
    return actors


def _real_http_app(w: Any, request_sessions: Any, person: Any) -> FastAPI:
    """Route is the production /hitl/queue/{item_id}/approve; only auth/session fixtures are overridden."""
    app = FastAPI()
    app.include_router(hitl_router.router, prefix="/api/v1")

    async def tenant_from_fixture() -> Any:
        return w.tenant_id

    async def member_from_fixture() -> Any:
        return person

    async def request_db() -> Any:
        async with request_sessions() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                {"tenant_id": str(w.tenant_id)},
            )
            yield session

    async def hitl_service(db: AsyncSession = Depends(request_db)) -> Any:
        return SimpleNamespace(
            review_queue_repo=SqlAlchemyReviewQueueRepository(session=db, tenant_id=w.tenant_id)
        )

    async def resume_use_case(db: AsyncSession = Depends(request_db)) -> ResumeWorkflowUseCase:
        return ResumeWorkflowUseCase(
            review_queue_repo=SqlAlchemyReviewQueueRepository(session=db, tenant_id=w.tenant_id),
            checkpoint_service=CheckpointService(checkpointer=w.saver),
            graph_app=w.app,
            claim_session_factory=w.sessions,
        )

    app.dependency_overrides[get_current_tenant_id] = tenant_from_fixture
    app.dependency_overrides[get_current_user] = member_from_fixture
    app.dependency_overrides[get_hitl_service] = hitl_service
    app.dependency_overrides[get_resume_workflow_use_case] = resume_use_case
    return app


async def _post_approve_http(w: Any, request_sessions: Any, person: Any) -> Any:
    async with AsyncClient(
        transport=ASGITransport(app=_real_http_app(w, request_sessions, person)),
        base_url="http://hitl-test.local",
    ) as client:
        return await client.post(
            f"/api/v1/hitl/queue/{w.review_item_id}/approve",
            json={"row_id": str(w.review_row_id)},
            headers={"Authorization": "Bearer isolated-test-principal"},
        )


async def test_sec04_http_zero_findings_refused_in_enforce_audit_and_off_with_zero_state_mutations(
    db: AsyncSession, empty_actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = empty_actors.w
    person = await empty_actors.user(label="sec04-human")
    await empty_actors.grant(person, READ, FIND, APPROVE)
    before = await _footprint(db, w)
    original_ledger = await _ledger(db, w)
    assert original_ledger == [] and before["resume_operations"] == 0

    for mode in ("enforce", "audit", "off"):
        await empty_actors.mode(mode)
        response = await _post_approve_http(w, request_sessions, person)
        assert response.status_code == 409, (mode, response.text)
        detail = response.json()["detail"]
        assert detail["code"] == "reconciliation_blocks_approval", (mode, detail)
        assert "NO_REVIEWABLE_FINDINGS" in detail["blockers"], (mode, detail)
        after = await _footprint(db, w)
        assert after == before, f"{mode}: no operation, event, analysis, review or trust-state mutation"
        assert after["resume_operations"] == 0 and after["review"] == "PENDING_REVIEW_REQUIRED"
        assert [row[1] for row in after["artifacts"]].count("trusted") == 0
        assert await _ledger(db, w) == original_ledger, "provisional HITL ledger unchanged"


async def test_sec04_direct_resume_zero_findings_is_refused_before_any_operation(
    db: AsyncSession, empty_actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = empty_actors.w
    human = await empty_actors.user(label="sec04-resume")
    await empty_actors.grant(human, READ, FIND, APPROVE)
    baseline = await _footprint(db, w)
    with pytest.raises(HTTPException) as denied:
        await _final(w, request_sessions, "resume", human)
    assert denied.value.status_code == 409
    assert denied.value.detail["code"] == "reconciliation_blocks_approval"
    assert "NO_REVIEWABLE_FINDINGS" in denied.value.detail["blockers"]
    assert await _footprint(db, w) == baseline
    assert await _ledger(db, w) == []


async def test_sec04_http_project_grant_and_cross_tenant_denials_are_not_weakened(
    db: AsyncSession, empty_actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = empty_actors.w
    before = await _footprint(db, w)
    no_grant = await empty_actors.user(label="sec04-without-grant")
    denied = await _post_approve_http(w, request_sessions, no_grant)
    assert denied.status_code in (403, 404), denied.text
    assert denied.status_code != 409, "authorization must fail before coverage is queried"

    foreign_actor = SimpleNamespace(
        id=uuid4(), tenant_id=uuid4(), role=UserRole.USER,
        is_active=True, full_name="Foreign tenant test actor",
    )
    foreign = await _post_approve_http(w, request_sessions, foreign_actor)
    assert foreign.status_code in (403, 404), foreign.text
    assert await _footprint(db, w) == before
    assert await _ledger(db, w) == []
