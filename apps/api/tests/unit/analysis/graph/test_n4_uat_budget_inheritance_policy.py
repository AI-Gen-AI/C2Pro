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
