"""PC-2b.1 (#920): the read-only WBS Domain Profile catalog endpoint.

TS-UW-PC2B1-API-001. ``GET /api/v1/wbs/profiles`` lists the locked catalog with the exact pins a
change set may carry. It is authenticated, read-only (no write method exists) and exposes no
run / generate endpoint.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.wbs.adapters.http.profile_catalog_router import router
from src.wbs.intelligence.profiles.catalog import default_catalog

pytestmark = pytest.mark.asyncio


def _app(*, authenticated: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    if authenticated:
        async def _user() -> SimpleNamespace:
            return SimpleNamespace(tenant_id=uuid4(), id=uuid4())

        app.dependency_overrides[get_current_user] = _user
    return app


async def _request(app: FastAPI, method: str = "GET") -> tuple[int, dict]:  # type: ignore[type-arg]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, "/api/v1/wbs/profiles")
    return response.status_code, response.json() if response.content else {}


async def test_the_catalog_lists_the_locked_profiles_with_their_exact_pins() -> None:
    status, body = await _request(_app())
    assert status == 200
    assert body["schema_version"] == "wbs-domain-profile/v1"
    listed = {(p["profile_id"], p["profile_version"]): p for p in body["profiles"]}
    assert set(listed) == {("civil_linear", "1.0.0"), ("software", "1.0.0"), ("solar_pv", "1.0.0")}
    solar = listed[("solar_pv", "1.0.0")]
    assert solar["pin"] == default_catalog().get("solar_pv", "1.0.0").pin()
    assert "solar_pv:mv_system" in solar["decomposition_kinds"]
    assert solar["advisory"] is True


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_the_catalog_is_read_only(method: str) -> None:
    status, _ = await _request(_app(), method)
    assert status == 405


async def test_no_run_or_generate_endpoint_is_exposed() -> None:
    paths = {route.path for route in router.routes}  # type: ignore[attr-defined]
    assert paths == {"/wbs/profiles"}


async def test_the_catalog_requires_authentication() -> None:
    status, _ = await _request(_app(authenticated=False))
    assert status in {401, 403}
