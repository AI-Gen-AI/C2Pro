"""PC-2b.3 (#922) -- WBS import API on a real PostgreSQL (TS-INT-PC2B3-WBS-IMPORT-API-001).

The minimal surface (parse a WBS source revision, read it, create a DRAFT from it, compare), the
"actor only from the session" rule, the api-principal refusal, idempotent parses and the absence
of any AI review / generate / auto-apply / schedule-as-WBS route.
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
from src.wbs.adapters.http.import_router import get_wbs_import_service
from src.wbs.adapters.http.import_router import router as import_router
from src.wbs.adapters.persistence.governance_repository import Actor
from src.wbs.imports.service import WBSImportService
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _scope, _user
from tests.modules.integration.test_pc2b3_wbs_import import PLANT_CSV, STORE, _wbs_document

pytestmark = pytest.mark.asyncio


def _app(db: AsyncSession, tenant_id: Any, actor: Actor) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(import_router, prefix="/api/v1")

    async def service() -> AsyncIterator[WBSImportService]:
        yield WBSImportService(db, storage=STORE)  # type: ignore[arg-type]

    app.dependency_overrides[get_wbs_import_service] = service
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(tenant_id=tenant_id, id=actor.user_id,
                                                                         role=actor.role)
    return app


async def _call(db: AsyncSession, s: Scope, actor: Actor, method: str, path: str, json: Any = None,
                params: dict[str, str] | None = None) -> Any:
    async with AsyncClient(transport=ASGITransport(app=_app(db, s.tenant, actor)), base_url="http://testserver") as client:
        response = await client.request(method, f"/api/v1/projects/{s.project}/wbs-imports{path}", json=json,
                                        params=params)
    if response.status_code < 400:
        await db.commit()
    else:
        await db.rollback()
    return response


async def test_a_human_parses_reads_creates_a_candidate_and_compares(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, revision_id = await _wbs_document(db, s, PLANT_CSV)
    created = await _call(db, s, s.author, "POST", "", {"document_id": str(document_id)})
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["status"], body["format"], body["parser_id"], body["parser_version"]) == ("READY", "csv", "wbs-csv",
                                                                                           "v1")
    assert body["revision_id"] == str(revision_id) and body["row_count"] == 4 and body["reused"] is False
    again = await _call(db, s, s.admin, "POST", "", {"document_id": str(document_id), "parse_config": {}})
    assert again.status_code == 200 and again.json()["id"] == body["id"] and again.json()["reused"] is True
    read = await _call(db, s, s.admin, "GET", f"/{body['id']}")
    assert read.status_code == 200 and read.json()["snapshot_digest"] == body["snapshot_digest"]
    candidate = await _call(db, s, s.author, "POST", f"/{body['id']}/candidates", {"title": "Imported plant WBS"})
    assert candidate.status_code == 201, candidate.text
    assert candidate.json() | {"change_set_id": None} == {
        "change_set_id": None, "source_import_id": body["id"], "entry_mode": "IMPORT_REVIEW", "origin": "import",
        "status": "DRAFT", "revision": 2, "node_count": 4}
    comparison = await _call(db, s, s.author, "GET", f"/{body['id']}/comparison",
                             params={"change_set_id": candidate.json()["change_set_id"]})
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["proposed"]["status"] == "NOT_AVAILABLE"
    assert {r["status"] for r in comparison.json()["rows"]} == {"UNCHANGED"}


async def test_the_api_principal_and_unknown_fields_are_refused(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    api = await _user(db, s.tenant, UserRole.API)
    refused = await _call(db, s, api, "POST", "", {"document_id": str(document_id)})
    assert refused.status_code == 403 and refused.json()["error_code"] == "WBS_IMPORT_FORBIDDEN"
    smuggled = await _call(db, s, s.author, "POST", "", {"document_id": str(document_id), "created_by": str(uuid4())})
    assert smuggled.status_code == 422
    bad_config = await _call(db, s, s.author, "POST", "", {"document_id": str(document_id),
                                                           "parse_config": {"sheet": "x"}})
    assert bad_config.status_code == 422 and bad_config.json()["error_code"] == "WBS_IMPORT_CONFIG_INVALID"
    missing = await _call(db, s, s.author, "GET", f"/{uuid4()}")
    assert missing.status_code == 404


async def test_no_ai_generate_auto_apply_or_schedule_import_route() -> None:
    paths = {route.path for route in import_router.routes}  # type: ignore[attr-defined]
    assert paths == {"/projects/{project_id}/wbs-imports", "/projects/{project_id}/wbs-imports/{import_id}",
                     "/projects/{project_id}/wbs-imports/{import_id}/candidates",
                     "/projects/{project_id}/wbs-imports/{import_id}/comparison"}
    for forbidden in ("generate", "review", "optimize", "apply", "approve", "schedule", "model"):
        assert not any(forbidden in path for path in paths), forbidden
