"""
C2Pro - Authentication Dependency Tests
TS-E2E-SEC-TNT-001
"""

from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.core.auth import bootstrap_lookup
from src.core.auth.bootstrap_lookup import (
    BootstrapFallbackBlockedError,
    BootstrapTenantRecord,
    BootstrapUserRecord,
    lookup_user_by_email,
)
from src.core.auth.dependencies import _provision_clerk_user
from src.core.auth.models import Tenant, User


@pytest.mark.asyncio
async def test_provision_clerk_user_uses_bootstrap_org_lookup(db, monkeypatch):
    """Should resolve existing Clerk org tenants via bootstrap lookup."""
    tenant = Tenant(
        id=uuid4(),
        name="Clerk Org Tenant",
        slug="clerk-org-tenant",
        clerk_org_id="org_12345678",
        is_active=True,
    )
    db.add(tenant)
    await db.commit()

    tenant_lookup = AsyncMock(
        return_value=BootstrapTenantRecord(
            tenant_id=tenant.id,
            is_active=True,
            clerk_org_id=tenant.clerk_org_id,
            tenant_name=tenant.name,
        )
    )
    user_lookup = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_tenant_by_clerk_org_id",
        tenant_lookup,
        raising=False,
    )
    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_user_by_clerk_user_id",
        user_lookup,
        raising=False,
    )

    user = await _provision_clerk_user(
        db=db,
        clerk_user_id="user_clerk_123",
        clerk_org_id=tenant.clerk_org_id,
        email="clerk@example.com",
        first_name="Clerk",
        last_name="Member",
    )

    tenant_lookup.assert_awaited_once_with(db, tenant.clerk_org_id)
    user_lookup.assert_awaited_once_with(db, "user_clerk_123")
    assert user.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_provision_clerk_user_uses_bootstrap_personal_tenant_lookup(db, monkeypatch):
    """Should resolve personal tenants via bootstrap lookup before creating users."""
    tenant = Tenant(
        id=uuid4(),
        name="Personal-user_cler",
        slug="personal-user-cler",
        is_active=True,
    )
    db.add(tenant)
    await db.commit()

    personal_lookup = AsyncMock(
        return_value=BootstrapTenantRecord(
            tenant_id=tenant.id,
            is_active=True,
            tenant_name=tenant.name,
        )
    )
    user_lookup = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_personal_tenant_by_name",
        personal_lookup,
        raising=False,
    )
    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_user_by_clerk_user_id",
        user_lookup,
        raising=False,
    )

    user = await _provision_clerk_user(
        db=db,
        clerk_user_id="user_clerk_123",
        clerk_org_id=None,
        email="personal@example.com",
        first_name="Personal",
        last_name="Member",
    )

    personal_lookup.assert_awaited_once_with(db, "Personal-user_cle")
    user_lookup.assert_awaited_once_with(db, "user_clerk_123")
    assert user.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_provision_clerk_user_uses_bootstrap_user_lookup_before_reassignment(db, monkeypatch):
    """Should resolve existing Clerk users through bootstrap lookup before tenant moves."""
    old_tenant = Tenant(
        id=uuid4(),
        name="Old Tenant",
        slug="old-tenant",
        is_active=True,
    )
    new_tenant = Tenant(
        id=uuid4(),
        name="New Tenant",
        slug="new-tenant",
        clerk_org_id="org_reassign",
        is_active=True,
    )
    db.add_all([old_tenant, new_tenant])
    await db.commit()

    existing_user = User(
        id=uuid4(),
        tenant_id=old_tenant.id,
        clerk_user_id="user_clerk_reassign",
        email="move@example.com",
        is_active=True,
    )
    db.add(existing_user)
    await db.commit()

    tenant_lookup = AsyncMock(
        return_value=BootstrapTenantRecord(
            tenant_id=new_tenant.id,
            is_active=True,
            clerk_org_id=new_tenant.clerk_org_id,
            tenant_name=new_tenant.name,
        )
    )
    user_lookup = AsyncMock(
        return_value=BootstrapUserRecord(
            user_id=existing_user.id,
            tenant_id=existing_user.tenant_id,
            email=existing_user.email,
            is_active=True,
            clerk_user_id=existing_user.clerk_user_id,
        )
    )

    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_tenant_by_clerk_org_id",
        tenant_lookup,
        raising=False,
    )
    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_user_by_clerk_user_id",
        user_lookup,
        raising=False,
    )

    user = await _provision_clerk_user(
        db=db,
        clerk_user_id=str(existing_user.clerk_user_id),
        clerk_org_id=new_tenant.clerk_org_id,
        email=existing_user.email,
        first_name="Move",
        last_name="User",
    )

    tenant_lookup.assert_awaited_once_with(db, new_tenant.clerk_org_id)
    user_lookup.assert_awaited_once_with(db, str(existing_user.clerk_user_id))
    assert user.tenant_id == new_tenant.id


def test_bootstrap_fallback_mode_blocks_production(monkeypatch):
    """Should deny fallback in production when mode is non_production."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_bootstrap_fallback_mode", "non_production", raising=False)

    assert bootstrap_lookup.is_bootstrap_fallback_allowed() is False


def test_bootstrap_fallback_mode_allows_test_environment(monkeypatch):
    """Should allow fallback in test when mode is non_production."""
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "auth_bootstrap_fallback_mode", "non_production", raising=False)

    assert bootstrap_lookup.is_bootstrap_fallback_allowed() is True


def test_bootstrap_ci_guard_blocks_orm_fallback_in_production(monkeypatch):
    """Production policy should emit blocked resolution, never orm_fallback."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_bootstrap_fallback_mode", "deny")
    monkeypatch.setattr(settings, "auth_bootstrap_emit_metrics", True)

    with patch("src.core.auth.bootstrap_lookup.logger.info") as mock_info:
        with pytest.raises(BootstrapFallbackBlockedError):
            bootstrap_lookup._handle_sql_failure(
                operation="ci_guard",
                error=SQLAlchemyError("forced bootstrap SQL failure"),
            )

    calls = [call.kwargs for call in mock_info.call_args_list]
    assert any(call.get("resolution_path") == "blocked" for call in calls)
    assert all(call.get("resolution_path") != "orm_fallback" for call in calls)


@pytest.mark.asyncio
async def test_bootstrap_sql_path_emits_resolution_telemetry(monkeypatch):
    """SQL success path should emit bootstrap_sql resolution telemetry."""
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "auth_bootstrap_fallback_mode", "non_production")
    monkeypatch.setattr(settings, "auth_bootstrap_emit_metrics", True)

    db = Mock()
    nested_ctx = AsyncMock()
    nested_ctx.__aenter__.return_value = None
    nested_ctx.__aexit__.return_value = False
    db.begin_nested.return_value = nested_ctx

    result = Mock()
    mappings = Mock()
    mappings.one_or_none.return_value = {
        "user_id": uuid4(),
        "tenant_id": uuid4(),
        "email": "bootstrap@example.com",
        "is_active": True,
        "hashed_password": "hash",
        "role": "user",
    }
    result.mappings.return_value = mappings
    db.execute = AsyncMock(return_value=result)

    with patch("src.core.auth.bootstrap_lookup.logger.info") as mock_info:
        record = await lookup_user_by_email(db, "bootstrap@example.com")

    assert record is not None
    resolution_calls = [call.kwargs for call in mock_info.call_args_list if call.args[0] == "auth_bootstrap_resolution"]
    assert any(call.get("resolution_path") == "bootstrap_sql" for call in resolution_calls)


@pytest.mark.asyncio
async def test_orm_fallback_path_emits_resolution_telemetry_when_allowed(monkeypatch):
    """Allowed SQL failure should emit orm_fallback telemetry and return ORM result."""
    tenant_id = uuid4()
    user_id = uuid4()

    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "auth_bootstrap_fallback_mode", "non_production")
    monkeypatch.setattr(settings, "auth_bootstrap_emit_metrics", True)

    db = Mock()
    nested_ctx = AsyncMock()
    nested_ctx.__aenter__.return_value = None
    nested_ctx.__aexit__.return_value = False
    db.begin_nested.return_value = nested_ctx

    orm_user = SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
        email="fallback@example.com",
        is_active=True,
        hashed_password="hash",
        role=None,
        clerk_user_id=None,
    )
    orm_result = Mock()
    orm_result.scalar_one_or_none.return_value = orm_user

    db.execute = AsyncMock(side_effect=[SQLAlchemyError("forced SQL path failure"), orm_result])

    with patch("src.core.auth.bootstrap_lookup.logger.info") as mock_info:
        record = await lookup_user_by_email(db, "fallback@example.com")

    assert record is not None
    assert record.user_id == user_id
    resolution_calls = [call.kwargs for call in mock_info.call_args_list if call.args[0] == "auth_bootstrap_resolution"]
    assert any(call.get("resolution_path") == "orm_fallback" for call in resolution_calls)
    assert any(call.get("fallback_blocked_by_policy") is False for call in resolution_calls)
