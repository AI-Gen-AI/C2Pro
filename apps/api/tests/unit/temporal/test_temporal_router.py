"""TS-UT-P0C-TEMPORAL-003 - project change timeline HTTP contract."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.temporal.adapters.http.router import get_event_repository, get_project_repository, router
from src.temporal.domain.project_event import ProjectEvent


class _Events:
    def __init__(self, events: list[ProjectEvent]) -> None:
        self.events = events

    async def list_for_project(self, project_id, tenant_id, since=None, limit=None):  # noqa: ANN001
        return [event for event in self.events if event.project_id == project_id and event.tenant_id == tenant_id]

    async def page_for_project(self, project_id, tenant_id, *, after, limit):  # noqa: ANN001
        rows = sorted(
            (event for event in self.events if event.project_id == project_id and event.tenant_id == tenant_id),
            key=lambda event: (event.occurred_at, event.event_id),
        )
        if after is not None:
            rows = [event for event in rows if (event.occurred_at, event.event_id) > (after.occurred_at, after.event_id)]
        return rows[: limit + 1]

    async def get_change_for_revision(self, *, tenant_id, project_id, document_id, revision_id):  # noqa: ANN001
        for event in self.events:
            if event.tenant_id != tenant_id or event.project_id != project_id:
                continue
            if event.event_type not in {"revision.changed", "revision.reinterpreted"} or event.source_revision_id not in {None, revision_id}:
                continue
            if event.payload.get("document_id") == str(document_id):
                return event
        return None


class _Projects:
    def __init__(self, owned: bool) -> None:
        self.owned = owned

    async def exists_by_id(self, project_id, tenant_id):  # noqa: ANN001
        return self.owned


def _event(project_id, tenant_id, document_id, revision_id) -> ProjectEvent:  # noqa: ANN001
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectEvent(
        event_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        event_type="revision.changed",
        payload={
            "state": "ready",
            "change_cause": "BUSINESS_STATE_CHANGED",
            "document_id": str(document_id),
            "changeset": {"changes": [{"before": {"full_text": "A"}, "after": {"full_text": "B"}}]},
            "provenance": {"target_revision_id": str(revision_id)},
            "l3_impact": None,
        },
        occurred_at=now,
        created_at=now,
    )


def _app(events: list[ProjectEvent], tenant_id, *, owned: bool = True) -> FastAPI:  # noqa: ANN001
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _user() -> SimpleNamespace:
        return SimpleNamespace(tenant_id=tenant_id)

    async def _events() -> _Events:
        return _Events(events)

    async def _projects() -> _Projects:
        return _Projects(owned)

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_event_repository] = _events
    app.dependency_overrides[get_project_repository] = _projects
    return app


@pytest.mark.asyncio
async def test_timeline_returns_ready_change_with_cause_and_provenance() -> None:
    """TS-UT-P0C-TEMPORAL-003: the user gets a durable ready temporal event."""
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    app = _app([_event(project_id, tenant_id, document_id, revision_id)], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["state"] == "ready"
    assert body["items"][0]["change_cause"] == "BUSINESS_STATE_CHANGED"
    assert body["items"][0]["provenance"]["target_revision_id"] == str(revision_id)
    assert body["items"][0]["l3_impact"] is None


@pytest.mark.asyncio
async def test_change_detail_is_cross_tenant_indistinguishable_404() -> None:
    """TS-UT-P0C-TEMPORAL-003: tenant B learns neither project nor change existence."""
    owner_tenant, caller_tenant = uuid4(), uuid4()
    project_id, document_id, revision_id = uuid4(), uuid4(), uuid4()
    app = _app([_event(project_id, owner_tenant, document_id, revision_id)], caller_tenant, owned=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}"
        )

    assert response.status_code == 404
    assert str(owner_tenant) not in response.text


@pytest.mark.asyncio
async def test_change_detail_rejects_a_different_document_in_the_same_project() -> None:
    """TS-UT-P0C-TEMPORAL-003: document/revision path ownership fails closed."""
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    app = _app([_event(project_id, tenant_id, document_id, revision_id)], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project_id}/documents/{uuid4()}/changes/{revision_id}"
        )

    assert response.status_code == 404


def test_timeline_paths_are_present_in_openapi() -> None:
    """TS-UT-P0C-TEMPORAL-003: product clients can discover both temporal endpoints."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    paths = app.openapi()["paths"]
    assert "/api/v1/projects/{project_id}/timeline" in paths
    assert "/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}" in paths
