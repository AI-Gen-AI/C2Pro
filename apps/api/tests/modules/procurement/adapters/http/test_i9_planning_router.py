"""
I9 - Procurement Planning HTTP Adapter
Test Suite ID: TS-I9-PROC-HTTP-001
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.modules.procurement.adapters.http.router import (
    get_procurement_planning_service,
    router,
)
from src.modules.procurement.application.ports import PlanningDecision


class _FakePlanningService:
    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> PlanningDecision:
        return PlanningDecision(
            plan_fingerprint="f" * 64,
            conflicts=[{"reason_code": "LATE_ORDER_WINDOW", "impact": "HIGH"}],
            requires_human_review=True,
        )


class _FailingPlanningService:
    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> PlanningDecision:
        raise RuntimeError("snapshot unavailable")


@pytest.mark.asyncio
async def test_i9_planning_endpoint_returns_contract_fields() -> None:
    """I9 HTTP contract: endpoint must return fingerprint, conflicts, and review gate flag."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_procurement_planning_service] = lambda: _FakePlanningService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/procurement/planning",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "required_on_site": "2026-09-01",
            },
            headers={"X-Tenant-Id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("plan_fingerprint"), str)
    assert len(payload["plan_fingerprint"]) == 64
    assert isinstance(payload.get("conflicts"), list)
    assert payload.get("requires_human_review") is True


@pytest.mark.asyncio
async def test_i9_planning_endpoint_maps_snapshot_failures_to_503() -> None:
    """I9 HTTP contract: snapshot retrieval failures must map to 503 for clients."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_procurement_planning_service] = lambda: _FailingPlanningService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/procurement/planning",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "required_on_site": "2026-09-01",
            },
            headers={"X-Tenant-Id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
        )

    assert response.status_code == 503, response.text
