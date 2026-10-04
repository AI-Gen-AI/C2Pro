"""TS-UT-P0C-TEMPORAL-003 - project change timeline HTTP contract."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.temporal.adapters.http.router import (
    get_event_repository,
    get_impact_assessor,
    get_project_repository,
    get_revision_projector,
    router,
)
from src.temporal.application.revision_projection import RevisionProjection
from src.temporal.domain.entity_ref import TemporalEntityRef
from src.temporal.domain.impact import ChangeImpact, ImpactAssessment, ImpactStatus
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


def _event(project_id, tenant_id, document_id, revision_id, *, engine="p0c-structural-l1-v2", basis="exact_content") -> ProjectEvent:  # noqa: ANN001
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
            "changeset": {"changes": [{"before": {"full_text": "A"}, "after": {"full_text": "B"}, "match_basis": basis}]},
            "provenance": {"target_revision_id": str(revision_id), "diff_engine_version": engine},
            "l3_impact": None,
        },
        confidence=1.0,
        occurred_at=now,
        created_at=now,
    )


def _app(events: list[ProjectEvent], tenant_id, *, owned: bool = True, impacts=None, projection=None) -> FastAPI:  # noqa: ANN001
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

    async def _assessor():  # noqa: ANN202
        async def assess(event, qualification):  # noqa: ANN001, ANN202
            return list(impacts or [])

        return assess

    async def _projector():  # noqa: ANN202
        async def project(*, project_id, document_id, revision_id, qualification):  # noqa: ANN001, ANN202
            return projection or RevisionProjection.none(revision_id, "no pending candidate for this revision")

        return project

    app.dependency_overrides[get_impact_assessor] = _assessor
    app.dependency_overrides[get_revision_projector] = _projector
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


@pytest.mark.asyncio
async def test_timeline_downgrades_a_legacy_matcher_event_without_mutating_it() -> None:
    """PR-C2: v1 matcher output is never presented as settled current intelligence."""
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    legacy = _event(project_id, tenant_id, document_id, revision_id, engine="p0c-structural-l1-v1", basis=None)
    stored = legacy.model_dump(mode="json")
    app = _app([legacy], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/timeline")

    item = response.json()["items"][0]
    assert item["state"] == "needs_review"
    assert item["legacy_matcher"] is True
    assert item["matcher_status"] == "legacy"
    assert item["confidence"] is None
    assert item["change_cause"] is None
    assert "p0c-structural-l1-v1" in item["qualification_reason"]
    assert item["provenance"]["diff_engine_version"] == "p0c-structural-l1-v1"
    assert legacy.model_dump(mode="json") == stored


@pytest.mark.asyncio
async def test_timeline_current_matcher_event_is_unaffected() -> None:
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    app = _app([_event(project_id, tenant_id, document_id, revision_id)], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/timeline")

    item = response.json()["items"][0]
    assert item["state"] == "ready"
    assert item["legacy_matcher"] is False
    assert item["matcher_status"] == "current"
    assert item["confidence"] == 1.0
    assert item["qualification_reason"] is None


@pytest.mark.asyncio
async def test_change_detail_exposes_impact_and_projection_separately() -> None:
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    impact = ChangeImpact(
        change_index=0,
        change_type="modified",
        source=TemporalEntityRef(
            artifact_type="contract", document_id=document_id, revision_id=uuid4(),
            entity_type="clause", entity_id=str(uuid4()), evidence=[],
        ),
        assessment=ImpactAssessment(status=ImpactStatus.UNKNOWN, items=[], confidence=None, reason="no persisted relationship"),
    )
    app = _app([_event(project_id, tenant_id, document_id, revision_id)], tenant_id, impacts=[impact])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}"
        )

    body = response.json()
    assert response.status_code == 200
    assert body["basis"] == "observed"
    assert body["impacts"][0]["assessment"]["status"] == "UNKNOWN"
    assert body["impacts"][0]["assessment"]["items"] == []
    assert body["impacts"][0]["source"]["entity_type"] == "clause"
    assert body["projection"]["status"] == "none"
    assert body["projection"]["basis"] == "projected"
    assert body["projection"]["projected_score"] is None


@pytest.mark.asyncio
async def test_change_detail_of_legacy_event_is_review_required() -> None:
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    legacy = _event(project_id, tenant_id, document_id, revision_id, engine="p0c-structural-l1-v1", basis=None)
    app = _app([legacy], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}"
        )

    body = response.json()
    assert body["state"] == "needs_review"
    assert body["legacy_matcher"] is True
    assert body["confidence"] is None


# --- PR #823: fail-safe dependencies -----------------------------------------------


class _NestedSession:
    """Just enough AsyncSession for savepoint-wrapped reads."""

    def begin_nested(self):  # noqa: ANN201
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _savepoint():  # noqa: ANN202
            yield None

        return _savepoint()


@pytest.mark.asyncio
async def test_resolver_failure_is_unknown_impact_never_a_partial_claim() -> None:
    from src.temporal.adapters.http.router import _FailClosedResolver

    class _Boom:
        entity_type = "clause"

        async def resolve(self, source):  # noqa: ANN001, ANN202
            raise RuntimeError("db down")

    source = TemporalEntityRef(
        artifact_type="contract", document_id=uuid4(), revision_id=uuid4(),
        entity_type="clause", entity_id=str(uuid4()), evidence=[],
    )
    result = await _FailClosedResolver(_Boom(), _NestedSession()).resolve(source)  # type: ignore[arg-type]

    assert result.source_verified is False
    assert result.links == []
    assert result.reason == "impact lookup unavailable"


@pytest.mark.asyncio
async def test_projection_read_failure_is_unavailable_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import asynccontextmanager

    import src.analysis.adapters.persistence.document_artifact_repository as artifacts
    from src.temporal.adapters.http import router as temporal_router
    from src.temporal.application.change_qualification import qualify_event

    @asynccontextmanager
    async def _session(_tenant):  # noqa: ANN001, ANN202
        yield _NestedSession()

    class _BrokenRepo:
        def __init__(self, _session) -> None:  # noqa: ANN001
            pass

        async def list_pending_candidates(self, **_):  # noqa: ANN003, ANN202
            raise RuntimeError("artifact store down")

    monkeypatch.setattr(temporal_router, "get_session_with_tenant", _session)
    monkeypatch.setattr(artifacts, "SqlAlchemyDocumentArtifactRepository", _BrokenRepo)
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    qualification = qualify_event(_event(project_id, tenant_id, document_id, revision_id))

    projector_gen = temporal_router.get_revision_projector(SimpleNamespace(tenant_id=tenant_id))
    project = await projector_gen.__anext__()
    projection = await project(
        project_id=project_id, document_id=document_id, revision_id=revision_id, qualification=qualification
    )
    await projector_gen.aclose()

    assert projection.status == "unavailable"
    assert projection.reason == "projection_read_failed"
    assert projection.projected_score is None
