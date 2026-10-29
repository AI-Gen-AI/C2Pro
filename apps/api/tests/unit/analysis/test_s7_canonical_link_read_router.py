"""S7: authenticated canonical-link reader cannot leak other tenants' approvals."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.analysis.adapters.http.technical_wbs_review_router import (
    get_canonical_technical_wbs_link_reader,
    router,
)
from src.analysis.application.list_canonical_technical_wbs_links import (
    CanonicalLinkProjectNotFound,
    CanonicalTechnicalWBSLinkView,
)
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PROJECT = UUID("22222222-2222-2222-2222-222222222222")
ACTOR = UUID("33333333-3333-3333-3333-333333333333")
EVENT = UUID("44444444-4444-4444-4444-444444444444")


class _Reader:
    def __init__(self, *, not_found: bool = False):
        self.calls = []
        self.not_found = not_found

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.not_found:
            raise CanonicalLinkProjectNotFound()
        return [
            CanonicalTechnicalWBSLinkView(
                event_id=EVENT,
                occurred_at=datetime(2026, 10, 29, tzinfo=UTC),
                review_event_id=UUID("55555555-5555-5555-5555-555555555555"),
                technical_document_id=UUID("66666666-6666-6666-6666-666666666666"),
                technical_revision_id=UUID("77777777-7777-7777-7777-777777777777"),
                source_clause_id=UUID("88888888-8888-8888-8888-888888888888"),
                source_section="4.1",
                wbs_baseline_id=UUID("99999999-9999-9999-9999-999999999999"),
                wbs_node_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                current_state="CURRENT_VERIFIED",
                state_reason="CURRENT_VERIFIED",
            )
        ]


def _app(reader, *, principal=True, clerk=True, active=True):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    if principal:
        app.dependency_overrides[get_current_user] = lambda: User(
            id=ACTOR,
            tenant_id=TENANT,
            email="s7-reader@example.invalid",
            hashed_password=None,
            clerk_user_id="clerk-s7-auth" if clerk else None,
            is_active=active,
        )
    app.dependency_overrides[get_canonical_technical_wbs_link_reader] = lambda: reader
    return app


@pytest.mark.asyncio
async def test_s7_get_requires_clerk_and_binds_tenant_from_session():
    reader = _Reader()
    async with AsyncClient(
        transport=ASGITransport(app=_app(reader)), base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/projects/{PROJECT}/technical-wbs/canonical-links")
    assert response.status_code == 200
    assert response.json()[0]["current_state"] == "CURRENT_VERIFIED"
    assert response.json()[0]["technical_assessment"] == "NOT_ASSESSED"
    assert reader.calls == [{"tenant_id": TENANT, "project_id": PROJECT, "limit": 50}]

    for app in (_app(_Reader(), clerk=False), _app(_Reader(), active=False)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/projects/{PROJECT}/technical-wbs/canonical-links")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_s7_get_foreign_project_is_neutral_and_no_unsigned_access():
    reader = _Reader(not_found=True)
    async with AsyncClient(
        transport=ASGITransport(app=_app(reader)), base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/projects/{PROJECT}/technical-wbs/canonical-links")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"

    async with AsyncClient(
        transport=ASGITransport(app=_app(_Reader(), principal=False)), base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/projects/{PROJECT}/technical-wbs/canonical-links")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_s7_get_rejects_unbounded_queries_before_reader():
    reader = _Reader()
    async with AsyncClient(
        transport=ASGITransport(app=_app(reader)), base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/projects/{PROJECT}/technical-wbs/canonical-links?limit=500")
    assert response.status_code == 422
    assert reader.calls == []
