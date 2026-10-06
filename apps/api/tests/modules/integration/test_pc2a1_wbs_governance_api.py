"""PC-2a.1 (#895) -- WBS governance READ API on a real PostgreSQL (TS-INT-PC2A1-WBS-API-001).

The API is read-only: authority, change sets (candidate trees served as proposals),
baseline history and the as-of view. It is tenant- and project-scoped and never returns a
candidate node as live WBS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import get_current_user
from src.core.handlers import register_exception_handlers
from src.wbs.adapters.http.governance_router import get_governance_repository, router
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import (
    Scope,
    _apply,
    _draft_with_tree,
    _legacy_nodes,
    _scope,
    _submit,
)

pytestmark = pytest.mark.asyncio


def _app(db: AsyncSession, tenant_id: UUID) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    async def repository() -> AsyncIterator[WBSGovernanceRepository]:
        yield WBSGovernanceRepository(db)

    app.dependency_overrides[get_governance_repository] = repository
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(tenant_id=tenant_id, id=uuid4())
    return app


async def _get(db: AsyncSession, s: Scope, path: str, **params: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=_app(db, s.tenant)), base_url="http://testserver") as client:
        return await client.get(f"/api/v1/projects/{s.project}/wbs-governance{path}", params=params)


def test_the_governance_api_is_read_only() -> None:
    methods = {method for route in router.routes if isinstance(route, APIRoute) for method in route.methods}
    assert methods == {"GET"}


async def test_authority_endpoint_reports_every_derived_state(db: AsyncSession) -> None:
    s = await _scope(db)
    body = (await _get(db, s, "/authority")).json()
    assert (body["state"], body["display_state"], body["approved"]) == ("NO_WBS", "NO_WBS", False)
    await _legacy_nodes(db, s.tenant, s.project, 23)
    legacy = (await _get(db, s, "/authority")).json()
    assert (legacy["state"], legacy["legacy_node_count"], legacy["approved"]) == ("LEGACY_UNGOVERNED", 23, False)
    change_set_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    pending = (await _get(db, s, "/authority")).json()
    assert pending["state"] == "LEGACY_UNGOVERNED" and pending["draft_exists"] is True and pending["approved"] is False
    baseline_id = await _apply(db, s, change_set_id, s.admin)
    approved = (await _get(db, s, "/authority")).json()
    assert (approved["state"], approved["baseline_id"], approved["baseline_no"]) == (
        "APPROVED_BASELINE", str(baseline_id), 1)
    assert approved["legacy_node_count"] == 0 and approved["tree_digest"].startswith("sha256:")


async def test_change_set_detail_serves_the_candidate_as_a_proposal(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    listing = (await _get(db, s, "/change-sets", status="DRAFT")).json()
    assert [item["id"] for item in listing] == [str(change_set_id)]
    assert (await _get(db, s, "/change-sets", status="APPLIED")).json() == []
    detail = (await _get(db, s, f"/change-sets/{change_set_id}")).json()
    assert detail["status"] == "DRAFT" and detail["origin"] == "manual" and detail["entry_mode"] == "GENERATE"
    assert {node["node_id"] for node in detail["nodes"]} == {str(v) for v in ids.values()}
    assert all(node["origin_kind"] == "minted" for node in detail["nodes"])
    assert detail["current_digest"].startswith("sha256:") and detail["submitted_digest"] is None
    digest = await _submit(db, s, change_set_id)
    submitted = (await _get(db, s, f"/change-sets/{change_set_id}")).json()
    assert submitted["submitted_digest"] == submitted["current_digest"] == digest


async def test_baseline_history_snapshot_and_as_of(db: AsyncSession) -> None:
    s = await _scope(db)
    t1 = datetime(2026, 2, 1, tzinfo=UTC)
    change_set_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    await _apply(db, s, change_set_id, s.admin, applied_at=t1)
    history = (await _get(db, s, "/baselines")).json()
    assert [b["baseline_no"] for b in history] == [1] and history[0]["source_change_set_id"] == str(change_set_id)
    snapshot = (await _get(db, s, "/baselines/1")).json()
    assert snapshot["digest_verified"] is True and len(snapshot["nodes"]) == snapshot["node_count"] == 3
    as_of = (await _get(db, s, "/baselines/as-of", at=(t1 + timedelta(hours=1)).isoformat())).json()
    assert as_of["baseline_no"] == 1
    assert (await _get(db, s, "/baselines/as-of", at=(t1 - timedelta(days=1)).isoformat())).status_code == 404
    assert (await _get(db, s, "/baselines/as-of", at="2026-02-01T00:00:00")).status_code == 422
    assert (await _get(db, s, "/baselines/2")).status_code == 404


async def test_other_tenants_cannot_read_governance_state(db: AsyncSession) -> None:
    owner = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, owner)
    intruder = await _scope(db)
    foreign = Scope(intruder.tenant, owner.project, intruder.author, intruder.admin, intruder.admin2)
    assert (await _get(db, foreign, "/authority")).status_code == 404
    assert (await _get(db, foreign, f"/change-sets/{change_set_id}")).status_code == 404
    # A change set id from another project of the caller's own tenant is not found either.
    other = await _scope(db)
    assert (await _get(db, other, f"/change-sets/{change_set_id}")).status_code == 404
