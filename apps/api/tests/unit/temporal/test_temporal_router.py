"""TS-UT-P0C-TEMPORAL-003 - project change timeline HTTP contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.temporal.adapters.http.router import (
    get_event_repository,
    get_impact_assessor,
    get_project_repository,
    get_revision_projector,
    get_revision_status_reader,
    router,
)
from src.temporal.application.change_qualification import CHANGE_EVENT_TYPES
from src.temporal.application.effective_change import OUTCOME_EVENT_TYPES, select_effective_outcome
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
        # Mirrors the SQL reader: the EFFECTIVE comparison, never "latest wins".
        candidates = [
            event for event in self.events
            if event.tenant_id == tenant_id and event.project_id == project_id
            and event.event_type in OUTCOME_EVENT_TYPES
            and event.source_revision_id in {None, revision_id}
            and event.payload.get("document_id") == str(document_id)
        ]
        effective = select_effective_outcome(candidates).effective
        return effective if effective is not None and effective.event_type in CHANGE_EVENT_TYPES else None

    @staticmethod
    def _revision_of(event: ProjectEvent):  # noqa: ANN205
        provenance = event.payload.get("provenance") or {}
        return event.source_revision_id or UUID(provenance["target_revision_id"])

    async def list_outcomes_for_revisions(self, *, tenant_id, revision_ids):  # noqa: ANN001
        return [
            event for event in self.events
            if event.tenant_id == tenant_id and event.event_type in OUTCOME_EVENT_TYPES
            and self._revision_of(event) in set(revision_ids)
        ]

    async def list_revision_outcomes(self, *, tenant_id, project_id, document_id, revision_id):  # noqa: ANN001
        return [
            event for event in await self.list_outcomes_for_revisions(tenant_id=tenant_id, revision_ids=[revision_id])
            if event.project_id == project_id and event.payload.get("document_id") == str(document_id)
        ]


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


def _app(events: list[ProjectEvent], tenant_id, *, owned: bool = True, impacts=None, projection=None, status=None) -> FastAPI:  # noqa: ANN001
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
    async def _status_reader():  # noqa: ANN202
        async def read(*, project_id, document_id, revision_id):  # noqa: ANN001, ANN202
            return status

        return read

    app.dependency_overrides[get_revision_projector] = _projector
    app.dependency_overrides[get_revision_status_reader] = _status_reader
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


# --- C3b-2: lineage, historical reads and revision status ----------------------------


def _recomputed(original: ProjectEvent, revision_id) -> ProjectEvent:  # noqa: ANN001
    event = _event(original.project_id, original.tenant_id, UUID(original.payload["document_id"]), revision_id)
    payload = dict(event.payload)
    payload["provenance"] = {
        **payload["provenance"],
        "recomputed_from_event_id": str(original.event_id),
        "recomputed_from_engine": "p0c-structural-l1-v1",
    }
    return event.model_copy(
        update={"event_type": "revision.recomputed", "payload": payload, "source_revision_id": revision_id}
    )


@pytest.mark.asyncio
async def test_timeline_marks_the_recomputation_effective_and_the_legacy_original_historical() -> None:
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    legacy = _event(
        project_id, tenant_id, document_id, revision_id, engine="p0c-structural-l1-v1", basis=None
    ).model_copy(update={"source_revision_id": revision_id})
    recomputed = _recomputed(legacy, revision_id)
    app = _app([legacy, recomputed], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/timeline")

    items = {item["event_id"]: item for item in response.json()["items"]}
    old, new = items[str(legacy.event_id)], items[str(recomputed.event_id)]
    # The legacy output stays visible, qualified, and can never pass for current.
    assert old["derivation"] == "original" and old["effective"] is False
    assert old["superseded_by_event_id"] == str(recomputed.event_id)
    assert old["legacy_matcher"] is True and old["state"] == "needs_review"
    assert new["derivation"] == "recomputed" and new["effective"] is True
    assert new["derived_from_event_id"] == str(legacy.event_id)
    assert new["matcher_status"] == "current" and new["superseded_by_event_id"] is None


@pytest.mark.asyncio
async def test_change_detail_returns_the_effective_comparison_with_its_history() -> None:
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    legacy = _event(
        project_id, tenant_id, document_id, revision_id, engine="p0c-structural-l1-v1", basis=None
    ).model_copy(update={"source_revision_id": revision_id})
    recomputed = _recomputed(legacy, revision_id)
    app = _app([recomputed, legacy], tenant_id)
    url = f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        effective = (await client.get(url)).json()
        historical = (await client.get(url, params={"event_id": str(legacy.event_id)})).json()
        unknown = await client.get(url, params={"event_id": str(uuid4())})

    assert effective["event_id"] == str(recomputed.event_id) and effective["effective"] is True
    assert {h["event_id"] for h in effective["history"]} == {str(legacy.event_id), str(recomputed.event_id)}
    # An explicit historical read is labelled as such, never as the current result.
    assert historical["event_id"] == str(legacy.event_id)
    assert historical["effective"] is False
    assert historical["superseded_by_event_id"] == str(recomputed.event_id)
    assert historical["state"] == "needs_review"
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_change_detail_cannot_read_another_revisions_event_by_id() -> None:
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()
    rev_a, rev_b = uuid4(), uuid4()
    other = _event(project_id, tenant_id, document_id, rev_b)
    app = _app([_event(project_id, tenant_id, document_id, rev_a), other], tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{rev_a}",
            params={"event_id": str(other.event_id)},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_change_detail_carries_revision_trust_and_materialization_status() -> None:
    from src.temporal.application.revision_status import MaterializationStatus, RevisionStatus

    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    status = RevisionStatus(
        revision_id=revision_id, rev_no=2, trust_state="trusted", is_current=True,
        current_revision_id=revision_id, current_basis="trusted",
        materialization=MaterializationStatus(
            state="materialized", scope="governance_authorized_effects_applied",
            qualifications=["WBS_GOVERNANCE_REQUIRED", "RISK_ALERT_RECONCILIATION_REQUIRED"],
            deferred_effects={"wbs": {"qualification": "WBS_GOVERNANCE_REQUIRED", "proposed_nodes": 3}},
        ),
    )
    app = _app([_event(project_id, tenant_id, document_id, revision_id)], tenant_id, status=status)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get(
            f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}"
        )).json()

    revision_status = body["revision_status"]
    assert revision_status["trust_state"] == "trusted" and revision_status["is_current"] is True
    assert revision_status["materialization"]["scope"] == "governance_authorized_effects_applied"
    assert "WBS_GOVERNANCE_REQUIRED" in revision_status["materialization"]["qualifications"]


@pytest.mark.asyncio
async def test_revision_status_read_failure_is_unavailable_never_current(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import asynccontextmanager

    import src.temporal.adapters.persistence.revision_status_reader as readers
    from src.temporal.adapters.http import router as temporal_router

    @asynccontextmanager
    async def _session(_tenant):  # noqa: ANN001, ANN202
        yield _NestedSession()

    class _BrokenReader:
        def __init__(self, _session) -> None:  # noqa: ANN001
            pass

        async def read(self, **_):  # noqa: ANN003, ANN202
            raise RuntimeError("store down")

    monkeypatch.setattr(temporal_router, "get_session_with_tenant", _session)
    monkeypatch.setattr(readers, "SqlAlchemyRevisionStatusReader", _BrokenReader)
    revision_id = uuid4()
    reader_gen = temporal_router.get_revision_status_reader(SimpleNamespace(tenant_id=uuid4()))
    read = await reader_gen.__anext__()
    status = await read(project_id=uuid4(), document_id=uuid4(), revision_id=revision_id)
    await reader_gen.aclose()

    assert status is not None and status.status == "unavailable"
    assert status.is_current is False and status.trust_state is None


@pytest.mark.asyncio
async def test_a_newer_failed_analysis_leaves_no_current_comparison_but_history_readable() -> None:
    tenant_id, project_id, document_id, revision_id = uuid4(), uuid4(), uuid4(), uuid4()
    comparison = _event(project_id, tenant_id, document_id, revision_id).model_copy(
        update={"source_revision_id": revision_id}
    )
    failed = comparison.model_copy(
        update={
            "event_id": uuid4(),
            "event_type": "revision.analysis_failed",
            "payload": {"state": "error", "document_id": str(document_id),
                        "provenance": {"target_revision_id": str(revision_id)}},
            "occurred_at": comparison.occurred_at + timedelta(minutes=5),
        }
    )
    app = _app([comparison, failed], tenant_id)
    url = f"/api/v1/projects/{project_id}/documents/{document_id}/changes/{revision_id}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        current = await client.get(url)
        historical = await client.get(url, params={"event_id": str(comparison.event_id)})

    # The effective outcome is the failure: no stale comparison is served as current.
    assert current.status_code == 404
    body = historical.json()
    assert body["event_id"] == str(comparison.event_id)
    assert body["effective"] is False
    assert body["superseded_by_event_id"] == str(failed.event_id)
    assert [h["event_type"] for h in body["history"]] == ["revision.changed", "revision.analysis_failed"]
