"""PC-2a.2 (#896) -- governed WBS command API on a real PostgreSQL (TS-INT-PC2A2-WBS-API-001).

The full human workflow over HTTP, error contracts, the "identity only from the session" rule
(#896 test 22) and the post-commit ProjectSnapshot seam (#896 test 42).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import src.temporal.application.project_snapshot_trigger as snapshot_trigger
from src.core.auth.dependencies import get_current_user
from src.core.handlers import register_exception_handlers
from src.temporal.domain.project_snapshot import SnapshotTrigger
from src.wbs.adapters.http.governance_router import get_governance_repository
from src.wbs.adapters.http.governance_router import router as read_router
from src.wbs.adapters.http.governed_change_router import get_governed_change_service
from src.wbs.adapters.http.governed_change_router import router as command_router
from src.wbs.adapters.persistence.governance_models import WBSBaselineORM
from src.wbs.adapters.persistence.governance_repository import Actor, WBSGovernanceRepository
from src.wbs.application.governed_change_service import WBSGovernedChangeService
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import (
    Scope,
    _legacy_nodes,
    _scope,
)

pytestmark = pytest.mark.asyncio


def _app(db: AsyncSession, tenant_id: UUID, actor: Actor) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(read_router, prefix="/api/v1")
    app.include_router(command_router, prefix="/api/v1")

    async def repository() -> AsyncIterator[WBSGovernanceRepository]:
        yield WBSGovernanceRepository(db)

    async def service() -> AsyncIterator[WBSGovernedChangeService]:
        yield WBSGovernedChangeService(db)

    app.dependency_overrides[get_governance_repository] = repository
    app.dependency_overrides[get_governed_change_service] = service
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(tenant_id=tenant_id, id=actor.user_id, role=actor.role)
    return app


async def _call(db: AsyncSession, s: Scope, actor: Actor, method: str, path: str, json: Any = None) -> Any:
    async with AsyncClient(transport=ASGITransport(app=_app(db, s.tenant, actor)), base_url="http://testserver") as client:
        response = await client.request(method, f"/api/v1/projects/{s.project}/wbs-governance{path}", json=json)
    await db.commit()
    return response


async def _command(db: AsyncSession, s: Scope, change_set_id: str, revision: int, command: dict[str, Any],
                   actor: Actor | None = None) -> Any:
    return await _call(db, s, actor or s.author, "POST", f"/change-sets/{change_set_id}/commands",
                       {"expected_revision": revision, "command": command})


async def _journey_to_submitted(db: AsyncSession, s: Scope) -> tuple[str, dict[str, Any]]:
    created = await _call(db, s, s.author, "POST", "/change-sets", {"title": "Baseline 1", "evidence_refs": ["doc:contract"]})
    assert created.status_code == 201, created.text
    change_set_id, revision = created.json()["id"], created.json()["revision"]
    civil = await _command(db, s, change_set_id, revision, {"type": "ADD_NODE", "node": {"name": "Civil", "code": "1"}})
    assert civil.status_code == 200, civil.text
    civil_id, revision = civil.json()["node_ids"][0], civil.json()["revision"]
    earth = await _command(db, s, change_set_id, revision,
                           {"type": "ADD_NODE", "parent_id": civil_id, "node": {"name": "Earthworks", "code": "1.1"}})
    revision = earth.json()["revision"]
    renamed = await _command(db, s, change_set_id, revision,
                             {"type": "UPDATE_NODE", "node_id": civil_id, "name": "Civil works",
                              "dictionary": {"scope_statement": "All civil works"}})
    assert renamed.status_code == 200, renamed.text
    revision = renamed.json()["revision"]
    submitted = await _call(db, s, s.author, "POST", f"/change-sets/{change_set_id}/submit", {"expected_revision": revision})
    assert submitted.status_code == 200, submitted.text
    return change_set_id, submitted.json()


async def test_the_full_governed_workflow_over_http(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s = await _scope(db)
    order: list[str] = []
    real_commit = db.commit

    async def commit() -> None:
        order.append("commit")
        await real_commit()

    def enqueue(**kwargs: Any) -> None:
        order.append("enqueue")
        assert kwargs["trigger"] is SnapshotTrigger.BASELINE_CHANGED and kwargs["project_id"] == s.project
        order.append(f"event:{kwargs['source_event_id']}")

    change_set_id, submitted = await _journey_to_submitted(db, s)
    monkeypatch.setattr(snapshot_trigger, "enqueue_project_snapshot", enqueue)
    monkeypatch.setattr(db, "commit", commit)
    approved = await _call(db, s, s.admin, "POST", f"/change-sets/{change_set_id}/approve",
                           {"expected_revision": submitted["submitted_revision"], "expected_digest": submitted["submitted_digest"]})
    monkeypatch.undo()
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert (body["status"], body["baseline_no"], body["change_set_digest"], body["snapshot_enqueued"]) == (
        "APPLIED", 1, submitted["submitted_digest"], True)
    # 42: the snapshot is dispatched only AFTER the apply transaction committed, from its event
    assert order.index("commit") < order.index("enqueue") and f"event:{body['event_id']}" in order
    authority = (await _call(db, s, s.author, "GET", "/authority")).json()
    assert (authority["state"], authority["baseline_no"], authority["tree_digest"]) == ("APPROVED_BASELINE", 1, body["tree_digest"])
    detail = (await _call(db, s, s.author, "GET", f"/change-sets/{change_set_id}")).json()
    assert detail["status"] == "APPLIED" and detail["retirements"] == []


async def test_a_failed_snapshot_dispatch_never_undoes_the_baseline(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s = await _scope(db)
    change_set_id, submitted = await _journey_to_submitted(db, s)

    def broken(**_kwargs: Any) -> None:
        raise ConnectionError("broker down")

    monkeypatch.setattr(snapshot_trigger, "enqueue_project_snapshot", broken)
    approved = await _call(db, s, s.admin, "POST", f"/change-sets/{change_set_id}/approve",
                           {"expected_revision": submitted["submitted_revision"], "expected_digest": submitted["submitted_digest"]})
    assert approved.status_code == 200 and approved.json()["snapshot_enqueued"] is False
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 1


async def test_22_reviewer_and_submitter_identity_cannot_be_client_supplied(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, submitted = await _journey_to_submitted(db, s)
    forged = await _call(db, s, s.author, "POST", f"/change-sets/{change_set_id}/approve",
                         {"expected_revision": submitted["submitted_revision"], "expected_digest": submitted["submitted_digest"],
                          "approved_by": str(s.admin.user_id)})
    assert forged.status_code == 422
    for path, body in (("/change-sets", {"title": "x", "created_by": str(s.admin.user_id)}),
                       (f"/change-sets/{change_set_id}/reject",
                        {"expected_revision": 1, "expected_digest": submitted["submitted_digest"], "reason": "x",
                         "decided_by": str(s.admin.user_id)})):
        assert (await _call(db, s, s.admin, "POST", path, body)).status_code == 422
    # the session user is the actor: a `user` session cannot approve even with a valid digest
    denied = await _call(db, s, s.author, "POST", f"/change-sets/{change_set_id}/approve",
                         {"expected_revision": submitted["submitted_revision"], "expected_digest": submitted["submitted_digest"]})
    assert denied.status_code == 403 and denied.json()["error_code"] == "WBS_GOVERNANCE_FORBIDDEN"
    detail = (await _call(db, s, s.author, "GET", f"/change-sets/{change_set_id}")).json()
    assert detail["status"] == "SUBMITTED"


async def test_error_contracts(db: AsyncSession) -> None:
    s = await _scope(db)
    created = (await _call(db, s, s.author, "POST", "/change-sets", {"title": "Errors"})).json()
    ok = await _command(db, s, created["id"], created["revision"], {"type": "ADD_NODE", "node": {"name": "A", "code": "1"}})
    stale = await _command(db, s, created["id"], created["revision"], {"type": "ADD_NODE", "node": {"name": "B", "code": "2"}})
    assert ok.status_code == 200 and stale.status_code == 409
    assert stale.json()["error_code"] == "CHANGE_SET_REVISION_CONFLICT"
    unknown = await _command(db, s, created["id"], ok.json()["revision"], {"type": "PATCH_ANYTHING", "sql": "x"})
    assert unknown.status_code == 422
    invalid = await _command(db, s, created["id"], ok.json()["revision"],
                             {"type": "UPDATE_NODE", "node_id": ok.json()["node_ids"][0], "dictionary": {"risk_ids": ["r"]}})
    assert invalid.status_code == 422 and invalid.json()["error_code"] == "WBS_CHANGE_SET_INVALID"
    missing = await _call(db, s, s.author, "POST", f"/change-sets/{s.project}/submit", {"expected_revision": 1})
    assert missing.status_code == 404
    other = await _scope(db)
    foreign = await _call(db, Scope(other.tenant, s.project, other.author, other.admin, other.admin2), other.author,
                          "POST", "/change-sets", {"title": "Intrusion"})
    assert foreign.status_code == 404


async def test_first_baseline_over_legacy_rows_over_http(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 3)
    created = (await _call(db, s, s.author, "POST", "/change-sets", {"title": "From schedule"})).json()
    adopted = await _command(db, s, created["id"], created["revision"], {"type": "ADOPT_LEGACY_NODE", "legacy_node_id": str(legacy[0])})
    assert adopted.status_code == 200 and adopted.json()["node_ids"] == [str(legacy[0])]
    submitted = (await _call(db, s, s.author, "POST", f"/change-sets/{created['id']}/submit",
                             {"expected_revision": adopted.json()["revision"]})).json()
    detail = (await _call(db, s, s.author, "GET", f"/change-sets/{created['id']}")).json()
    assert {r["node_id"] for r in detail["retirements"]} == {str(legacy[1]), str(legacy[2])}
    assert {r["disposition"] for r in detail["retirements"]} == {"RETIRED_ON_BASELINE"}
    approved = await _call(db, s, s.admin, "POST", f"/change-sets/{created['id']}/approve",
                           {"expected_revision": submitted["submitted_revision"], "expected_digest": submitted["submitted_digest"]})
    assert approved.status_code == 200, approved.text
    assert {r["node_id"] for r in approved.json()["retired"]} == {str(legacy[1]), str(legacy[2])}
