from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.ai.analytics_router import get_analytics_service, router
from src.core.security import get_current_tenant_id


class _StubAnalyticsService:
    def __init__(self) -> None:
        self.last_call: tuple[str, str, str] | None = None

    async def cost_breakdown(self, *, tenant_id, timeframe: str):
        self.last_call = ("cost", str(tenant_id), timeframe)
        return {"timeframe": timeframe, "series": [], "summary": {"total_cost": 0, "total_tokens": 0, "total_requests": 0}}

    async def version_performance(self, *, tenant_id, timeframe: str):
        self.last_call = ("versions", str(tenant_id), timeframe)
        return {"timeframe": timeframe, "versions": []}

    async def compare_versions(self, *, tenant_id, timeframe: str, baseline_version: str, candidate_version: str):
        self.last_call = ("comparison", str(tenant_id), timeframe)
        return {"timeframe": timeframe, "baseline": {"prompt_version": baseline_version}, "candidate": {"prompt_version": candidate_version}, "delta": {}}

    async def quality_drift(self, *, tenant_id, timeframe: str):
        if timeframe == "bad":
            raise ValueError("Invalid timeframe")
        self.last_call = ("quality-drift", str(tenant_id), timeframe)
        return {"timeframe": timeframe, "series": [], "alerts": []}


def _build_client() -> tuple[TestClient, _StubAnalyticsService, str]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    tenant_id = str(uuid4())
    stub = _StubAnalyticsService()

    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_analytics_service] = lambda: stub

    return TestClient(app), stub, tenant_id


def test_cost_endpoint_uses_tenant_context() -> None:
    client, stub, tenant_id = _build_client()

    response = client.get("/api/v1/ai/analytics/cost?timeframe=7d")

    assert response.status_code == 200
    assert stub.last_call == ("cost", tenant_id, "7d")


def test_quality_drift_maps_validation_error() -> None:
    client, _, _ = _build_client()

    response = client.get("/api/v1/ai/analytics/quality-drift?timeframe=bad")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid timeframe"
