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
from src.core.tenants.service import TenantService, get_tenant_by_id, list_tenants
from src.core.tenants.types import require_tenant_id


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


def test_core_tenants_create_schema_requires_the_live_tenant_fields():
    """Tenant creation keeps the name and slug boundary required by the API."""
    schema = tenants_schemas.TenantCreate(name="Core Test Tenant", slug="core-test-tenant")

    assert schema.model_dump() == {"name": "Core Test Tenant", "slug": "core-test-tenant"}


def test_core_tenant_service_retains_the_injected_database_session():
    """Tenant service construction uses the database session injected by the router."""
    db = SimpleNamespace()
    service = TenantService(db)

    assert service.db is db


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


@pytest.mark.asyncio
async def test_list_tenants_active_only_filters_with_a_sql_predicate() -> None:
    """TS-E2E-SEC-TNT-001: active-only filtering must not collapse to ``WHERE false``."""
    captured_statement = None
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    class _FakeSession:
        async def execute(self, statement):
            nonlocal captured_statement
            captured_statement = statement
            return result

    await list_tenants(_FakeSession(), active_only=True)

    assert captured_statement is not None
    assert "is_active" in str(captured_statement)
    assert "false" not in str(captured_statement).lower()


def test_require_tenant_id_parses_task_boundary_string() -> None:
    """TS-E2E-SEC-TNT-001: task strings become UUID-backed tenant IDs."""
    tenant_id = uuid4()

    normalized = require_tenant_id(str(tenant_id))

    assert normalized == tenant_id
    assert not isinstance(normalized, str)


def test_require_tenant_id_rejects_invalid_task_boundary_string() -> None:
    """TS-E2E-SEC-TNT-001: malformed task tenant IDs fail at the boundary."""
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        require_tenant_id("not-a-tenant-id")
