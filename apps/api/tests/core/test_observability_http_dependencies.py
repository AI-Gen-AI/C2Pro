"""
Observability HTTP dependency injection contracts.
Test Suite ID: TS-I12-OBS-HTTP-001
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.observability.router import (
    get_observability_service,
    router,
)
from src.core.security import get_current_tenant_id


class _FakeObservabilityService:
    async def get_system_status(self):
        return {
            "api_status": "ok",
            "database_status": "ok",
            "timestamp": datetime(2026, 1, 1, 12, 0, 0),
        }

    async def get_recent_analyses(self, limit: int, offset: int, tenant_id=None):
        return {
            "analyses": [
                {
                    "id": uuid4(),
                    "project_id": uuid4(),
                    "status": "COMPLETED",
                    "coherence_score": 87,
                    "alerts_count": 1,
                    "started_at": datetime(2026, 1, 1, 10, 0, 0),
                    "completed_at": datetime(2026, 1, 1, 10, 5, 0),
                }
            ],
            "total_analyses": 1,
        }


def test_i12_status_route_uses_overridable_service_dependency() -> None:
    """TS-I12-OBS-HTTP-001: status route must use a FastAPI-injected service dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_observability_service] = lambda: _FakeObservabilityService()
    app.dependency_overrides[get_current_tenant_id] = lambda: uuid4()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/v1/observability/status")

    assert response.status_code == 200, response.text
    assert response.json()["api_status"] == "ok"


def test_i12_recent_analyses_route_uses_overridable_service_dependency() -> None:
    """TS-I12-OBS-HTTP-001: recent analyses route must use a FastAPI-injected service dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_observability_service] = lambda: _FakeObservabilityService()
    app.dependency_overrides[get_current_tenant_id] = lambda: uuid4()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/v1/observability/analyses")

    assert response.status_code == 200, response.text
    assert response.json()["total_analyses"] == 1


def test_i12_observability_routes_expose_bearer_auth_in_openapi() -> None:
    """TS-I12-OBS-HTTP-001: protected observability routes must advertise bearer auth."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    openapi = app.openapi()

    assert openapi["paths"]["/api/v1/observability/status"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
    assert openapi["paths"]["/api/v1/observability/analyses"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
