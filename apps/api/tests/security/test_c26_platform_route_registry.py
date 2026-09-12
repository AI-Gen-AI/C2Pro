import pytest
from fastapi import Depends, FastAPI

from src.admin.adapters.http.router import router as cross_tenant_admin_router
from src.core.auth.platform_operator import require_platform_operator
from src.core.dlq.router import router as legacy_tenant_router
from src.core.middleware.tenant_isolation import (
    active_mounted_routes,
    assert_platform_route_registry,
)
from src.main import app


def test_registered_platform_routes_are_exactly_one_active_cross_tenant_mount() -> None:
    assert_platform_route_registry(app)


def test_legacy_tenant_dlq_router_is_not_mounted_in_production_app() -> None:
    endpoint_modules = {
        route.endpoint.__module__
        for route in active_mounted_routes(app)
    }

    assert "src.core.dlq.router" not in endpoint_modules


def test_second_identical_mounted_route_makes_the_structural_gate_red() -> None:
    fixture_app = FastAPI()
    fixture_app.include_router(cross_tenant_admin_router, prefix="/api/v1")
    fixture_app.include_router(legacy_tenant_router, prefix="/api/v1")

    with pytest.raises(AssertionError, match="exactly one"):
        assert_platform_route_registry(fixture_app)


def test_unregistered_platform_operator_route_makes_the_structural_gate_fail() -> None:
    fixture_app = FastAPI()
    fixture_app.include_router(cross_tenant_admin_router, prefix="/api/v1")

    @fixture_app.get(
        "/api/v1/admin/dlq/audit",
        dependencies=[Depends(require_platform_operator)],
    )
    async def unregistered_platform_route() -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(AssertionError, match="absent from the registry"):
        assert_platform_route_registry(fixture_app)
