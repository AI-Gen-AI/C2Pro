"""TS-E2E-SEC-TNT-001: Tenant budget response and isolation contract coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.router import get_tenant_service, router
from src.core.tenants.schemas import BudgetStatusResponse
from src.core.tenants.service import TenantService


@pytest.mark.asyncio
async def test_budget_service_returns_declared_response_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-E2E-SEC-TNT-001: The service returns the router's declared response model."""
    tenant_id = uuid4()
    tenant = SimpleNamespace(
        id=tenant_id,
        ai_budget_monthly=100.0,
        ai_spend_current=25.0,
        budget_usage_percentage=25.0,
        is_over_budget=False,
        ai_spend_last_reset=datetime(2026, 1, 1, tzinfo=UTC),
    )
    service = TenantService(cast(AsyncSession, object()))

    async def _get_tenant(_: UUID) -> Any:
        return tenant

    monkeypatch.setattr(service, "get_tenant", _get_tenant)

    result = await service.get_budget_status(tenant_id)

    assert isinstance(result, BudgetStatusResponse)
    assert result.tenant_id == str(tenant_id)


class _BudgetService:
    """TS-E2E-SEC-TNT-001: Minimal tenant-owned budget service double."""

    def __init__(self, owned_tenant_id: UUID) -> None:
        self._owned_tenant_id = owned_tenant_id

    async def get_budget_status(self, tenant_id: UUID) -> BudgetStatusResponse | None:
        if tenant_id != self._owned_tenant_id:
            return None
        return BudgetStatusResponse(
            tenant_id=str(tenant_id),
            monthly_budget=100.0,
            current_spend=25.0,
            remaining=75.0,
            usage_percentage=25.0,
            is_over_budget=False,
            last_reset=None,
        )


def _client(service: _BudgetService) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_tenant_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_budget_route_returns_declared_response_shape_for_owned_tenant() -> None:
    """TS-E2E-SEC-TNT-001: Owned tenant budget payload matches the public contract."""
    tenant_id = uuid4()

    response = _client(_BudgetService(tenant_id)).get(f"/api/v1/tenants/{tenant_id}/budget")

    assert response.status_code == 200, response.text
    assert BudgetStatusResponse.model_validate(response.json()).tenant_id == str(tenant_id)


@pytest.mark.parametrize("tenant_id", [uuid4(), uuid4()])
def test_budget_route_hides_missing_and_foreign_tenants(tenant_id: UUID) -> None:
    """TS-E2E-SEC-TNT-001: Missing and foreign tenants share the non-leaking 404 contract."""
    response = _client(_BudgetService(uuid4())).get(f"/api/v1/tenants/{tenant_id}/budget")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found"}
