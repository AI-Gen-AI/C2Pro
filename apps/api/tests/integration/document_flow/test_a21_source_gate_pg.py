"""A21: HTTP approval must not trust source-ineligible persisted findings."""


import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.core.auth.dependencies import get_current_user
from src.core.security import get_current_tenant_id, get_current_user_id_with_bearer
from src.modules.hitl.adapters.http import router as hitl
from src.modules.hitl.adapters.http.dependencies import get_hitl_service, get_resume_workflow_use_case
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.human_in_the_loop_service import HumanInTheLoopService
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
from tests.integration.document_flow import test_s5_hitl_reject_and_differentiated_approval as subject
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
    world,  # noqa: F401
    worker,  # noqa: F401
    real_saver,  # noqa: F401
    independent_sessions,  # noqa: F401
    request_sessions,  # noqa: F401
    _clean_recovery_discovery_rows,  # noqa: F401
    _status,
    _submission,
    _ledger,
)
from tests.integration.document_flow.test_s5_granular_finding_routes_pg import _post
from src.modules.hitl.adapters.checkpoint_service import CheckpointService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def source_variant(request, monkeypatch):
    variant = request.param
    risk = dict(subject.RISKS[0])
    if variant != "absent":
        risk.update(
            source_quote=subject.COMPLETION_CLAUSE if variant == "verified" else (
                "   " if variant == "blank" else None
            ),
            source_quote_status="UNVERIFIED" if variant == "unverified" else "VERIFIED",
        )
    monkeypatch.setattr(subject, "RISKS", [risk])
    return variant


@pytest.mark.parametrize("source_variant", ["verified", "unverified", "absent", "blank"], indirect=True)
async def test_persisted_source_gate_over_http(db, test_user, world, request_sessions, source_variant):
    w = world
    receipt = await _post(w, test_user, _submission(w, ordinal=0, expected=0))
    assert receipt.ledger_revision == 1
    before = await _status(db, w)
    ledger_before = await _ledger(db, w)

    async def request_repo():
        async with request_sessions() as session:
            await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"),
                                  {"t": str(w.tenant_id)})
            try:
                yield SqlAlchemyReviewQueueRepository(session=session, tenant_id=w.tenant_id)
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def service(repo=Depends(request_repo)):
        return HumanInTheLoopService(repo, None, None)

    async def resume(repo=Depends(request_repo)):
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=CheckpointService(checkpointer=w.saver),
            graph_app=w.app,
            claim_session_factory=w.sessions,
        )

    app = FastAPI()
    app.include_router(hitl.router)
    app.dependency_overrides[get_current_tenant_id] = lambda: w.tenant_id
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_current_user_id_with_bearer] = lambda: test_user.id
    app.dependency_overrides[get_hitl_service] = service
    app.dependency_overrides[get_resume_workflow_use_case] = resume
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/hitl/queue/{w.review_item_id}/approve", json={"row_id": str(w.review_row_id)}
        )
        after = await _status(db, w)
        if source_variant == "verified":
            assert response.status_code == 200, response.text
            assert after["review"] == "APPROVED"
            assert after["artifacts"][-1][1] == "trusted"
            assert after["artifacts"][-1][3] == w.artifact_hash
            async def physical_row():
                await db.commit()
                return (await db.execute(
                    text("SELECT to_jsonb(r) - 'current_status' FROM review_items r WHERE id = :r"),
                    {"r": w.review_row_id},
                )).scalar_one()

            row_before = await physical_row()
            release = await client.post(f"/hitl/queue/{w.review_row_id}/release")
            assert release.status_code == 200, release.text
            assert release.json()["current_status"] == "CLOSED"
            assert await physical_row() == row_before
            closed = await _status(db, w)
            assert closed["review"] == "CLOSED"
            assert closed["artifacts"] == after["artifacts"]
        else:
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "reconciliation_blocks_approval", response.text
            assert after == before
        assert await _ledger(db, w) == ledger_before
