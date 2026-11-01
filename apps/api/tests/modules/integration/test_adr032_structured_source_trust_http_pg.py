"""ADR-032 authenticated HTTP contract + real PostgreSQL readback.

The Clerk principal is test-injected (HTTP -> RLS -> DB path); this is not browser Clerk UAT.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.http import structured_source_trust_router as routes
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import Tenant, User
from tests.modules.integration.test_adr032_structured_source_trust_pg import (
    _approver,
    _document,
    _Storage,
    _verifier,
    _world,
)

pytestmark = pytest.mark.asyncio


async def test_http_request_decide_and_error_mapping(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver_id = await _approver(db, w)
    requester = await db.get(User, w["actor"])
    approver = await db.get(User, approver_id)
    assert requester is not None and approver is not None
    doc = await _document(db, w, tmp_path, storage)
    monkeypatch.setattr(routes, "_verifier", lambda: _verifier(storage))

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: requester
    url = f"/api/v1/documents/{doc['document']}/revisions/{doc['revision']}/trust-candidate"
    body = {"idempotency_key": "http-adr032-request", "reason": "Please consider this source"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(url, json=body)
        assert created.status_code == 201, created.text
        data = created.json()
        assert data["trust_state"] == "proposed" and data["replayed"] is False
        assert data["source_assessment"] == "NOT_ASSESSED" and data["family"] == "budget"
        replay = await client.post(url, json=body)
        assert replay.status_code == 201 and replay.json()["replayed"] is True
        assert replay.json()["artifact_id"] == data["artifact_id"]
        # Foreign / unknown revision and non-current revision are mapped, never a 500.
        missing = await client.post(
            f"/api/v1/documents/{doc['document']}/revisions/{uuid4()}/trust-candidate", json=body
        )
        assert missing.status_code == 404 and missing.json()["detail"]["code"] == "not_found"
        # Client cannot smuggle actor/tenant fields.
        smuggled = await client.post(url, json={**body, "actor_user_id": str(uuid4())})
        assert smuggled.status_code == 422

    decision = {
        "review_row_id": data["review_row_id"], "artifact_id": data["artifact_id"],
        "artifact_version": data["artifact_version"], "artifact_hash": data["artifact_hash"],
        "decision": "APPROVE", "idempotency_key": "http-adr032-decide", "reason": "Exact source approved",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Self-approval without the audited exception -> 403 with the separation reason.
        own = await client.post("/api/v1/structured-source-trust/decisions", json=decision)
        assert own.status_code == 403 and "separation of duties" in own.json()["detail"]["message"]
        app.dependency_overrides[get_current_user] = lambda: approver
        stale = await client.post(
            "/api/v1/structured-source-trust/decisions", json={**decision, "artifact_version": 99}
        )
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_candidate"
        ok = await client.post("/api/v1/structured-source-trust/decisions", json=decision)
        assert ok.status_code == 200, ok.text
        assert ok.json()["trust_state"] == "trusted" and ok.json()["self_approved"] is False
        assert ok.json()["authority"] == "EXPLICIT_HUMAN_STRUCTURED_SOURCE_TRUST"
        again = await client.post("/api/v1/structured-source-trust/decisions", json=decision)
        assert again.status_code == 200 and again.json()["replayed"] is True
        conflicting = await client.post(
            "/api/v1/structured-source-trust/decisions",
            json={**decision, "decision": "REJECT", "idempotency_key": "http-adr032-other"},
        )
        assert conflicting.status_code == 409 and conflicting.json()["detail"]["code"] == "already_decided"

    stranger = User(
        id=uuid4(), tenant_id=uuid4(), email=f"adr032-{uuid4().hex}@example.invalid",
        clerk_user_id=f"adr032-{uuid4().hex}", is_active=True, is_verified=False,
    )
    app.dependency_overrides[get_current_user] = lambda: stranger
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.post(url, json=body)
        assert denied.status_code == 404
        denied_decision = await client.post("/api/v1/structured-source-trust/decisions", json=decision)
        assert denied_decision.status_code == 404


async def test_http_self_approval_exception_is_honoured_and_recorded(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    requester = await db.get(User, w["actor"])
    assert requester is not None
    doc = await _document(db, w, tmp_path, storage)
    await db.execute(
        update(Tenant).where(Tenant.id == w["tenant"]).values(
            settings={"trust_governance": {"structured_source_self_approval": True}}
        )
    )
    await db.commit()
    monkeypatch.setattr(routes, "_verifier", lambda: _verifier(storage))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: requester
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = (await client.post(
            f"/api/v1/documents/{doc['document']}/revisions/{doc['revision']}/trust-candidate",
            json={"idempotency_key": "http-adr032-self-req", "reason": "Single-human tenant"},
        )).json()
        out = await client.post("/api/v1/structured-source-trust/decisions", json={
            "review_row_id": created["review_row_id"], "artifact_id": created["artifact_id"],
            "artifact_version": created["artifact_version"], "artifact_hash": created["artifact_hash"],
            "decision": "APPROVE", "idempotency_key": "http-adr032-self-dec", "reason": "Self approval, audited",
        })
    assert out.status_code == 200 and out.json()["self_approved"] is True
    assert (await db.scalar(select(Tenant.settings).where(Tenant.id == w["tenant"])))["trust_governance"]


async def test_legacy_hitl_routes_answer_409_and_expose_the_exact_candidate(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    """The legacy approve/reject routes refuse a bound thread-less review (409, review untouched);
    the queue response carries the exact binding the reviewer must decide."""
    from types import SimpleNamespace

    from fastapi import HTTPException

    from src.analysis.application.structured_source_trust import RequestStructuredSourceTrustService
    from src.modules.hitl.adapters.http import router as hitl_router
    from src.modules.hitl.adapters.http.schemas import ApproveRequest, RejectRequest
    from src.modules.hitl.adapters.notifications.log_notification_service import (
        LogNotificationService,
    )
    from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
    from src.modules.hitl.application.human_in_the_loop_service import HumanInTheLoopService
    from src.modules.hitl.domain.entities import ReviewStatus
    from src.modules.hitl.domain.services import ConfidenceRouter

    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    async with test_session_factory() as session:
        receipt = await RequestStructuredSourceTrustService(session, _verifier(storage)).execute(
            tenant_id=w["tenant"], document_id=doc["document"], revision_id=doc["revision"],
            actor_user_id=w["actor"], idempotency_key="http-adr032-legacy", reason="legacy guard",
        )
        await session.commit()

    async with test_session_factory() as session:
        service = HumanInTheLoopService(
            review_queue_repo=SqlAlchemyReviewQueueRepository(session=session, tenant_id=w["tenant"]),
            notification_service=LogNotificationService(),
            confidence_router=ConfidenceRouter(),
        )
        user = SimpleNamespace(id=w["actor"], full_name="Legacy Route User")
        with pytest.raises(HTTPException) as approve:
            await hitl_router.approve_item(
                doc["document"], ApproveRequest(row_id=receipt.review_row_id), w["tenant"], user,
                service, None,  # type: ignore[arg-type]
            )
        assert approve.value.status_code == 409
        assert "structured-source-trust/decisions" in str(approve.value.detail)
        with pytest.raises(HTTPException) as reject:
            await hitl_router.reject_item(
                doc["document"], RejectRequest(reason="no", row_id=receipt.review_row_id), w["tenant"],
                user, service, None,  # type: ignore[arg-type]
            )
        assert reject.value.status_code == 409
        review = await service.review_queue_repo.get_review_item_by_row_id(receipt.review_row_id)  # type: ignore[attr-defined]
        assert review is not None and review.current_status is ReviewStatus.PENDING_REVIEW_REQUIRED
        response = hitl_router._to_review_item_response(review)
        assert response.trust_kind == "structured_source" and response.resumable is False
        assert response.candidate_binding is not None
        assert response.candidate_binding["artifact_hash"] == receipt.artifact_hash
        assert response.decision_ready is True
