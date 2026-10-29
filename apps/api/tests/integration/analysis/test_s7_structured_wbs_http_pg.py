"""S7 authenticated HTTP contract + real PostgreSQL readback for Budget and Schedule.

Clerk principal is test-injected, so this proves the HTTP-RLS-DB path and
never counts as genuine Clerk logout/relogin browser UAT.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.http import structured_wbs_link_router as routes
from src.analysis.application.canonical_structured_wbs_links import ImmutableXLSXRowReader
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from tests.integration.analysis.test_s7_review_service_settlement_pg import _world
from tests.integration.analysis.test_s7_structured_wbs_three_source_pg import (
    _SyntheticImmutableStorage, _structured_document,
)

pytestmark = pytest.mark.asyncio


async def test_s7_http_post_get_two_types_across_new_sessions_denies_foreign_tenant(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = await _world(db, tmp_path)
    actor = await db.get(User, w["actor"])
    assert actor is not None and actor.clerk_user_id

    files: dict[str, Path] = {}
    budget = await _structured_document(db, w, tmp_path, "budget", files)
    schedule = await _structured_document(db, w, tmp_path, "schedule", files)
    verified_reader = ImmutableXLSXRowReader(
        _SyntheticImmutableStorage(files), ExcelFileParser(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(routes, "_reader", lambda: verified_reader)

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: actor
    endpoint = f"/api/v1/projects/{w['project']}/structured-wbs/canonical-links"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(endpoint)).json() == []

    for item in (budget, schedule):
        body = {
            **item, "expected_wbs_baseline_id": str(w["baseline"]),
            "expected_wbs_node_id": str(w["node"]),
            "approval": "APPROVE_CANONICAL_LINK",
            "idempotency_key": f"s7-httpsrc-{item['family']}-key",
            "reason": "Clerk-bound human confirms exact row and approved WBS",
        }
        for key in ("source_document_id", "source_revision_id"):
            body[key] = str(body[key])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            post = await client.post(endpoint, json=body)
            assert post.status_code == 201, post.text
            assert post.json()["authority"] == "EXPLICIT_HUMAN_CANONICAL_LINK"
            assert post.json()["source_assessment"] == "NOT_ASSESSED"
            replay = await client.post(endpoint, json=body)
            assert replay.status_code == 201
            assert replay.json()["replayed"] is True
            assert replay.json()["event_id"] == post.json()["event_id"]
            assert (await client.post(endpoint, json={
                **body, "expected_wbs_baseline_id": str(uuid4())
            })).status_code == 409

    # Close the original clients and read from another independent tenant-scoped
    # SQLAlchemy session via actual request dependencies.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        latest = await client.get(endpoint)
        assert latest.status_code == 200, latest.text
        links = latest.json()
        assert {v["family"] for v in links} == {"budget", "schedule"}
        assert all(v["state"] == "CURRENT" for v in links)
        assert all(v["wbs_node_id"] == str(w["node"]) for v in links)
        assert all(v["wbs_baseline_id"] == str(w["baseline"]) for v in links)
        assert (await client.get(endpoint, params={"limit": 51})).status_code == 422

    stranger = User(
        id=uuid4(), tenant_id=uuid4(),
        email=f"s7-external-{uuid4().hex}@example.invalid",
        clerk_user_id=f"s7-external-{uuid4().hex}",
        is_active=True, is_verified=False,
    )
    app.dependency_overrides[get_current_user] = lambda: stranger
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get(endpoint)
        assert denied.status_code == 404, denied.text
        assert denied.json()["detail"] == "Project not found"
