"""ACC-01 S7 review API: authenticated principal is never client-controlled."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.analysis.adapters.http.technical_wbs_review_router import (
    get_technical_wbs_review_service,
    router,
)
from src.analysis.application.record_technical_wbs_review import (
    TechnicalMappingDecision,
    TechnicalMappingReviewError,
    TechnicalMappingReviewResult,
)
from src.analysis.domain.technical_wbs_link_candidate import TechnicalWBSLinkCandidate
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PROJECT = UUID("22222222-2222-2222-2222-222222222222")
USER = UUID("33333333-3333-3333-3333-333333333333")
CLAUSE = UUID("44444444-4444-4444-4444-444444444444")
REVISION = UUID("55555555-5555-5555-5555-555555555555")
DOCUMENT = UUID("66666666-6666-6666-6666-666666666666")
BASELINE = UUID("77777777-7777-7777-7777-777777777777")
NODE = UUID("88888888-8888-8888-8888-888888888888")


def _body() -> dict[str, str]:
    return {
        "clause_id": str(CLAUSE),
        "expected_revision_id": str(REVISION),
        "expected_blob_hash": "a" * 64,
        "expected_wbs_baseline_id": str(BASELINE),
        "proposed_wbs_node_id": str(NODE),
        "decision": "CONFIRMED_FOR_REVIEW",
        "idempotency_key": "review-identity-key",
        "reason": "Engineer examined section source and WBS hierarchy",
    }


class _ReviewService:
    def __init__(self, exception: Exception | None = None) -> None:
        self.arguments: list[dict] = []
        self.exception = exception

    async def execute(self, **kwargs):
        self.arguments.append(kwargs)
        if self.exception:
            raise self.exception
        candidate = TechnicalWBSLinkCandidate(
            tenant_id=TENANT,
            project_id=PROJECT,
            technical_document_id=DOCUMENT,
            technical_revision_id=REVISION,
            source_blob_hash="a" * 64,
            source_clause_id=CLAUSE,
            source_section="4.1.2",
            source_start_offset=0,
            source_end_offset=78,
            proposed_wbs_baseline_id=BASELINE,
            proposed_wbs_node_id=NODE,
        )
        return TechnicalMappingReviewResult(
            event_id=uuid4(),
            candidate=candidate,
            decision=TechnicalMappingDecision.CONFIRMED_FOR_REVIEW,
            replayed=False,
        )


def _app(service: _ReviewService, *, login: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    if login:
        app.dependency_overrides[get_current_user] = lambda: User(
            id=USER,
            tenant_id=TENANT,
            email="test-s7-auth@example.invalid",
            hashed_password=None,
            clerk_user_id="clerk-test-s7",
            is_active=True,
            is_verified=True,
        )
    app.dependency_overrides[get_technical_wbs_review_service] = lambda: service
    return app


@pytest.mark.asyncio
async def test_authenticated_actor_is_session_principal_not_request_body() -> None:
    service = _ReviewService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/projects/{PROJECT}/technical-wbs/reviews", json=_body()
        )
    assert response.status_code == 201, response.text
    assert len(service.arguments) == 1
    args = service.arguments[0]
    assert args["actor_user_id"] == USER
    assert args["tenant_id"] == TENANT
    assert args["project_id"] == PROJECT
    assert args["clause_id"] == CLAUSE
    assert response.json()["authority"] == "AUDIT_ONLY_NOT_CANONICAL_LINK"
    assert response.json()["approved_canonical_link"] is False
    assert response.json()["technical_assessment"] == "NOT_ASSESSED"
    assert response.json()["state"] == "HUMAN_REVIEW_REQUIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unauthorized",
    [
        {"actor_user_id": str(uuid4())},
        {"tenant_id": str(uuid4())},
        {"project_id": str(uuid4())},
        {"approved_canonical_link": True},
        {"technical_assessment": "COMPLIANT"},
    ],
)
async def test_forbids_client_supplied_authority(unauthorized: dict) -> None:
    service = _ReviewService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/projects/{PROJECT}/technical-wbs/reviews",
            json={**_body(), **unauthorized},
        )
    assert response.status_code == 422
    assert service.arguments == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TechnicalMappingReviewError("project unavailable to this tenant"), 404),
        (TechnicalMappingReviewError("technical clause or immutable revision not found"), 404),
        (TechnicalMappingReviewError("authenticated human reviewer required"), 403),
        (TechnicalMappingReviewError("the approved WBS baseline changed"), 409),
    ],
)
async def test_denies_foreign_sources_reviewers_and_stale_authority(
    error: Exception, code: int
) -> None:
    service = _ReviewService(error)
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/projects/{PROJECT}/technical-wbs/reviews", json=_body()
        )
    assert response.status_code == code
    assert "not found" in response.text or "denied" in response.text or "changed" in response.text


@pytest.mark.asyncio
async def test_unauthed_user_cannot_reach_review_service() -> None:
    service = _ReviewService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service, login=False)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/projects/{PROJECT}/technical-wbs/reviews", json=_body()
        )
    assert response.status_code in (401, 403)
    assert service.arguments == []


@pytest.mark.asyncio
async def test_invalid_sha_rejected_without_execution() -> None:
    service = _ReviewService()
    body = _body()
    body["expected_blob_hash"] = "not-a-hash"
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/projects/{PROJECT}/technical-wbs/reviews", json=body
        )
    assert response.status_code == 422
    assert service.arguments == []
