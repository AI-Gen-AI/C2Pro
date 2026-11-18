"""Fail-closed budget inheritance switch. Tests never call external providers."""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.graph.n4_governed_bridge import (
    N4GraphBridgeBlocked,
    _uat_inherited_scopes,
)


def test_uat_budget_inheritance_disabled_by_default(monkeypatch):
    tenant = uuid4()
    monkeypatch.delenv("C2PRO_N4_UAT_INHERIT_SCOPES", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "uat")
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(tenant))
    assert _uat_inherited_scopes(tenant) is False


@pytest.mark.parametrize("environment", ["production", "", "development"])
def test_budget_inheritance_rejects_non_uat_runtime(monkeypatch, environment):
    tenant = uuid4()
    monkeypatch.setenv("C2PRO_N4_UAT_INHERIT_SCOPES", "1")
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(tenant))
    with pytest.raises(N4GraphBridgeBlocked, match="requires named UAT"):
        _uat_inherited_scopes(tenant)


def test_budget_inheritance_rejects_other_tenant(monkeypatch):
    monkeypatch.setenv("C2PRO_N4_UAT_INHERIT_SCOPES", "1")
    monkeypatch.setenv("ENVIRONMENT", "pilot")
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(uuid4()))
    with pytest.raises(N4GraphBridgeBlocked, match="approved tenant"):
        _uat_inherited_scopes(uuid4())


@pytest.mark.parametrize("environment", ["uat", "pilot"])
def test_budget_inheritance_allows_exact_scoped_uat(monkeypatch, environment):
    tenant = uuid4()
    monkeypatch.setenv("C2PRO_N4_UAT_INHERIT_SCOPES", "1")
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(tenant))
    assert _uat_inherited_scopes(tenant) is True


def test_railway_pilot_exact_environment_id_accepts_even_with_prod_runtime(monkeypatch):
    tenant = uuid4()
    env_id = str(uuid4())
    monkeypatch.setenv("C2PRO_N4_UAT_INHERIT_SCOPES", "1")
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(tenant))
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", env_id)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "pilot")
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", env_id)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert _uat_inherited_scopes(tenant) is True


@pytest.mark.parametrize("name,pin", [
    ("production", True), ("pilot", False),
])
def test_railway_scope_rejects_wrong_deployment_or_missing_pin(monkeypatch, name, pin):
    tenant = uuid4()
    actual = str(uuid4())
    monkeypatch.setenv("C2PRO_N4_UAT_INHERIT_SCOPES", "1")
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(tenant))
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", actual)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", name)
    if pin:
        monkeypatch.setenv(
            "C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", actual,
        )
    else:
        monkeypatch.delenv("C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "uat")
    with pytest.raises(N4GraphBridgeBlocked, match="pinned UAT"):
        _uat_inherited_scopes(tenant)
