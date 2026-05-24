"""
Alerts HTTP dependency contracts.
Test Suite ID: TS-I12-ALERTS-HTTP-001
"""

from __future__ import annotations

from fastapi import FastAPI

from src.alerts.adapters.http.router import project_alerts_router, router


def test_i12_alert_routes_expose_bearer_auth_in_openapi() -> None:
    """TS-I12-ALERTS-HTTP-001: protected alert routes must advertise bearer auth."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(project_alerts_router, prefix="/api/v1")

    openapi = app.openapi()

    assert openapi["paths"]["/api/v1/alerts/projects/{project_id}"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
    assert openapi["paths"]["/api/v1/projects/{project_id}/alerts"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
