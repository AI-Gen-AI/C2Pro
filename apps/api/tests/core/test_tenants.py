"""
C2Pro - Core Tenants Tests
TS-E2E-SEC-TNT-001
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import APIRouter

from src.core.tenants import __getattr__ as tenants_getattr
from src.core.tenants import router as tenants_router_module
from src.core.tenants import schemas as tenants_schemas
from src.core.tenants.service import TenantService, get_tenant_by_id


def test_core_tenants_getattr_imports_service_module():
    """Should lazily import the service module from package __getattr__."""
    module = tenants_getattr("service")

    assert module.__name__ == "src.core.tenants.service"


def test_core_tenants_getattr_rejects_unknown_attribute():
    """Should raise AttributeError for unsupported package attributes."""
    with pytest.raises(AttributeError):
        tenants_getattr("missing")


def test_core_tenants_router_exports_apirouter():
    """Should expose a FastAPI APIRouter for tenant routes."""
    assert isinstance(tenants_router_module.router, APIRouter)


def test_core_tenants_schema_accepts_empty_payload():
    """Should keep the placeholder tenant schema instantiable."""
    schema = tenants_schemas.Tenant()

    assert schema.model_dump() == {}


def test_core_tenant_service_placeholder_is_instantiable():
    """Should keep the placeholder service constructible for DI wiring."""
    service = TenantService()

    assert isinstance(service, TenantService)


@pytest.mark.asyncio
async def test_core_tenants_get_tenant_by_id_returns_scalar_result():
    """Should return the scalar tenant result from the async DB execution path."""
    tenant = SimpleNamespace(id=uuid4(), is_active=True)
    result = SimpleNamespace(scalar_one_or_none=lambda: tenant)

    class _FakeSession:
        async def execute(self, _statement):
            return result

    resolved = await get_tenant_by_id(_FakeSession(), tenant.id)

    assert resolved is tenant
