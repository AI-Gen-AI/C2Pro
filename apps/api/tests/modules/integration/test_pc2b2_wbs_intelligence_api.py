"""PC-2b.2 (#921) -- WBS intelligence API on a real PostgreSQL (TS-INT-PC2B2-WBS-INTELLIGENCE-API-001).

The minimal surface (request / get / cancel a run, list items, preview, decide), the "actor only
from the session" rule, the api-principal refusal, idempotent run requests and the absence of any
generate / model / import / optimizer / auto-apply route.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import UserRole
from src.core.handlers import register_exception_handlers
from src.wbs.adapters.http.intelligence_router import get_wbs_intelligence_service
from src.wbs.adapters.http.intelligence_router import router as intelligence_router
from src.wbs.adapters.persistence.governance_repository import Actor
from src.wbs.intelligence.application.service import WBSIntelligenceService
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _scope, _user
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _new, _rev, _tree
from tests.modules.integration.test_pc2b2_wbs_intelligence_store import _world

pytestmark = pytest.mark.asyncio


def _app(db: AsyncSession, tenant_id: Any, actor: Actor) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(intelligence_router, prefix="/api/v1")

    async def service() -> AsyncIterator[WBSIntelligenceService]:
        yield WBSIntelligenceService(db)

    app.dependency_overrides[get_wbs_intelligence_service] = service
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(tenant_id=tenant_id, id=actor.user_id,
                                                                         role=actor.role)
    return app


async def _call(db: AsyncSession, s: Scope, actor: Actor, method: str, path: str, json: Any = None) -> Any:
    async with AsyncClient(transport=ASGITransport(app=_app(db, s.tenant, actor)), base_url="http://testserver") as client:
        response = await client.request(method, f"/api/v1/projects/{s.project}/wbs-intelligence/runs{path}", json=json)
    if response.status_code < 400:
        await db.commit()
    else:
        await db.rollback()
    return response


async def test_a_human_requests_reads_and_reuses_a_deterministic_run(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    body = {"target_kind": "CANDIDATE", "change_set_id": str(change_set_id)}
    created = await _call(db, s, s.author, "POST", "", body)
    assert created.status_code == 201, created.text
    run = created.json()
    assert (run["status"], run["outcome"], run["execution_type"]) == ("COMPLETED", "COMPLETE", "DETERMINISTIC")
    assert run["model_provenance"] is None and run["freshness"] == {"state": "FRESH", "reasons": []}
    assert len(run["qualification"]["results"]) == 19
    again = await _call(db, s, s.author, "POST", "", body)
    assert again.status_code == 200 and again.json()["id"] == run["id"] and again.json()["reused"] is True
    rerun = await _call(db, s, s.author, "POST", "", {**body, "rerun": True})
    assert rerun.status_code == 201 and rerun.json()["id"] != run["id"]
    read = await _call(db, s, s.admin, "GET", f"/{run['id']}")
    assert read.status_code == 200 and read.json()["qualification_digest"] == run["qualification_digest"]
    items = await _call(db, s, s.author, "GET", f"/{run['id']}/items")
    assert items.status_code == 200 and all(i["kind"] == "FINDING" and i["decision"] is None for i in items.json())
    cancel = await _call(db, s, s.author, "POST", f"/{run['id']}/cancel")
    assert cancel.status_code == 409  # a terminal run is immutable


async def test_the_api_principal_and_unknown_fields_are_refused(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    api_user = await _user(db, s.tenant, UserRole.API)
    refused = await _call(db, s, api_user, "POST", "", {"target_kind": "CANDIDATE", "change_set_id": str(change_set_id)})
    assert refused.status_code == 403 and refused.json()["error_code"] == "WBS_INTELLIGENCE_FORBIDDEN"
    forged = await _call(db, s, s.author, "POST", "", {"target_kind": "CANDIDATE", "change_set_id": str(change_set_id),
                                                       "requested_by": str(uuid4())})
    assert forged.status_code == 422  # the actor never comes from the body
    for kind in ("NONE", "IMPORT", "GENERATE"):
        assert (await _call(db, s, s.author, "POST", "", {"target_kind": kind})).status_code == 422


async def test_preview_then_decide_over_http(db: AsyncSession) -> None:
    w = await _world(db)
    s = w.s
    selections = [{"item_id": str(w.item("p-mv")), "decision": "APPLY_AS_PROPOSED"},
                  {"item_id": str(w.item("p-cables")), "decision": "APPLY_AS_PROPOSED"}]
    preview = await _call(db, s, s.author, "POST", f"/{w.run_id}/preview",
                          {"change_set_id": str(w.change_set_id), "selections": selections})
    assert preview.status_code == 200, preview.text
    assert preview.json()["applicable"] is True
    assert {i["applicability"] for i in preview.json()["items"]} == {"APPLICABLE"}
    revision = await _rev(db, w.change_set_id)
    stale_revision = await _call(db, s, s.author, "POST", f"/{w.run_id}/decisions",
                                 {"change_set_id": str(w.change_set_id), "expected_revision": revision + 5,
                                  "decisions": selections})
    assert stale_revision.status_code == 409 and stale_revision.json()["error_code"] == "CHANGE_SET_REVISION_CONFLICT"
    approve = await _call(db, s, s.admin, "POST", f"/{w.run_id}/decisions",
                          {"decisions": [{"item_id": str(w.item("p-mv")), "decision": "APPROVE"}]})
    assert approve.status_code == 422  # no approval vocabulary exists here
    decided = await _call(db, s, s.author, "POST", f"/{w.run_id}/decisions",
                          {"change_set_id": str(w.change_set_id), "expected_revision": revision,
                           "decisions": [*selections, {"item_id": str(w.item("f-gran")), "decision": "ACKNOWLEDGE"}]})
    assert decided.status_code == 200, decided.text
    assert decided.json()["change_set_revision"] == revision + 2
    items = {i["ref"]: i for i in (await _call(db, s, s.author, "GET", f"/{w.run_id}/items")).json()}
    assert items["p-mv"]["decision"]["decision"] == "APPLY_AS_PROPOSED"
    assert items["f-gran"]["decision"]["decision"] == "ACKNOWLEDGE" and items["p-found"]["decision"] is None


async def test_the_surface_is_minimal() -> None:
    routes = {(method, route.path) for route in intelligence_router.routes for method in route.methods}  # type: ignore[attr-defined]
    base = "/projects/{project_id}/wbs-intelligence/runs"
    assert routes == {
        ("POST", base), ("GET", f"{base}/{{run_id}}"), ("POST", f"{base}/{{run_id}}/cancel"),
        ("GET", f"{base}/{{run_id}}/items"), ("POST", f"{base}/{{run_id}}/preview"),
        ("POST", f"{base}/{{run_id}}/decisions"),
    }
    for forbidden in ("generate", "llm", "model", "import", "optimiz", "auto", "approve"):
        assert not [path for _, path in routes if forbidden in path.lower()]
