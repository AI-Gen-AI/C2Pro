"""
I9 - Procurement Security Hardening (RED)
Test Suite ID: TS-SEC-I9-001
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.modules.procurement.adapters.http.router import (
    get_procurement_planning_service,
    router as procurement_router,
)
from src.modules.procurement.application.ports import PlanningDecision


class _FailingService:
    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> PlanningDecision:
        raise RuntimeError("db connection timeout on tenant shard bbbb")


class _CrossTenantService:
    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> PlanningDecision:
        raise ValueError("cross-tenant snapshot rows detected")


@pytest.mark.asyncio
async def test_sec_i9_missing_tenant_header_is_unauthorized_red() -> None:
    """TS-SEC-I9-001: missing tenant context must be rejected as unauthorized."""
    app = FastAPI()
    app.include_router(procurement_router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/procurement/planning",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "required_on_site": "2026-09-01",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sec_i9_runtime_error_does_not_leak_internal_details_red() -> None:
    """TS-SEC-I9-001: internal errors must be sanitized in outward-facing API responses."""
    app = FastAPI()
    app.include_router(procurement_router, prefix="/api/v1")
    app.dependency_overrides[get_procurement_planning_service] = lambda: _FailingService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/procurement/planning",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "required_on_site": "2026-09-01",
            },
            headers={"X-Tenant-Id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
        )

    assert response.status_code == 503
    assert "db connection timeout" not in response.text
    assert "tenant shard" not in response.text


@pytest.mark.asyncio
async def test_sec_i9_cross_tenant_violation_maps_to_forbidden_red() -> None:
    """TS-SEC-I9-001: cross-tenant snapshot detection must map to 403 forbidden."""
    app = FastAPI()
    app.include_router(procurement_router, prefix="/api/v1")
    app.dependency_overrides[get_procurement_planning_service] = lambda: _CrossTenantService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/procurement/planning",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "required_on_site": "2026-09-01",
            },
            headers={"X-Tenant-Id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
        )

    assert response.status_code == 403
