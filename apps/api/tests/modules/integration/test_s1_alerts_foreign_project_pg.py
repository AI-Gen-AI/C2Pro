"""S1: the project alerts routes never answer 200 for a project of ANOTHER tenant (404), in both directions,
even when that project has no alerts; an own project without alerts keeps answering 200 with an empty list."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.adapters.http import router as routes
from src.core.database import get_session
from src.core.security import get_current_tenant_id
from tests.integration.analysis.test_s7_review_service_settlement_pg import _world

pytestmark = pytest.mark.asyncio


async def test_foreign_project_alerts_are_404_both_ways_and_own_empty_is_200(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    a = await _world(db, tmp_path)
    (tmp_path / "b").mkdir()
    b = await _world(db, tmp_path / "b")
    assert a["tenant"] != b["tenant"] and a["project"] != b["project"]

    async def session():
        async with test_session_factory() as s:
            yield s

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.include_router(routes.project_alerts_router, prefix="/api/v1")
    app.dependency_overrides[get_session] = session
    paths = (
        lambda project: f"/api/v1/alerts/projects/{project}",
        lambda project: f"/api/v1/projects/{project}/alerts",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_current_tenant_id] = lambda: a["tenant"]
        for path in paths:
            own = await client.get(path(a["project"]))
            assert own.status_code == 200, own.text  # own project, no alerts
            foreign = await client.get(path(b["project"]))  # A -> B (B holds no alerts either)
            assert foreign.status_code == 404 and foreign.json()["detail"] == "Project not found"
            assert (await client.get(path(uuid4()))).status_code == 404  # unknown project
        app.dependency_overrides[get_current_tenant_id] = lambda: b["tenant"]
        for path in paths:
            assert (await client.get(path(a["project"]))).status_code == 404  # B -> A
            assert (await client.get(path(b["project"]))).status_code == 200
