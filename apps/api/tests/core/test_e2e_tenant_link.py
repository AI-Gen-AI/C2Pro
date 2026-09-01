"""The Clerk <-> local tenant linkage read-back.

TS-UT-P0B-TENANT-LINK-001.

This is a tenant boundary, so the checks must fail on every way the linkage can
be wrong -- a missing row, the wrong tenant, an absent or mismatched Clerk
identifier -- and must never leak a Clerk identifier into their output.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_e2e_tenant_link.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_e2e_tenant_link", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


link = _load()

_TENANT = link.DEFAULT_TENANT_ID
_ORG = "org_dedicated_e2e"
_CLERK_USER = "user_configured_e2e"


def _evaluate(
    tenant: dict[str, Any] | None, user: dict[str, Any] | None
) -> list[tuple[str, bool, str]]:
    return link.evaluate_tenant_link(
        tenant,
        user,
        expected_tenant_id=_TENANT,
        expected_org_id=_ORG,
        expected_user_clerk_id=_CLERK_USER,
    )


def _aligned() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {"id": _TENANT, "clerk_org_id": _ORG},
        {"id": link.DEFAULT_USER_ID, "tenant_id": _TENANT, "clerk_user_id": _CLERK_USER},
    )


def test_aligned_linkage_passes_all_four_equalities() -> None:
    checks = _evaluate(*_aligned())
    assert all(passed for _, passed, _ in checks)
    # tenant row, user row, tenant.id, tenant.clerk_org_id, user.clerk_user_id, user.tenant_id
    assert len(checks) == 6


def test_missing_tenant_row_fails_closed() -> None:
    checks = _evaluate(None, None)
    assert checks == [("tenant row exists", False, "tenant row not found")]


def test_missing_user_row_fails_closed() -> None:
    tenant, _ = _aligned()
    checks = _evaluate(tenant, None)
    assert not all(passed for _, passed, _ in checks)


@pytest.mark.parametrize(
    ("mutate_tenant", "mutate_user", "broken_check"),
    [
        (
            {"clerk_org_id": "org_someone_else"},
            {},
            "tenant.clerk_org_id is the dedicated E2E Organization",
        ),
        ({"clerk_org_id": None}, {}, "tenant.clerk_org_id is the dedicated E2E Organization"),
        (
            {},
            {"clerk_user_id": "user_someone_else"},
            "user.clerk_user_id is the configured E2E identity",
        ),
        ({}, {"clerk_user_id": None}, "user.clerk_user_id is the configured E2E identity"),
        (
            {},
            {"tenant_id": "11111111-1111-1111-1111-111111111111"},
            "user.tenant_id is the deterministic E2E tenant",
        ),
        (
            {"id": "11111111-1111-1111-1111-111111111111"},
            {},
            "tenant.id is the deterministic E2E tenant",
        ),
    ],
    ids=["wrong_org", "absent_org", "wrong_clerk_user", "absent_clerk_user", "wrong_user_tenant", "wrong_tenant"],
)
def test_each_broken_link_is_detected(
    mutate_tenant: dict[str, Any], mutate_user: dict[str, Any], broken_check: str
) -> None:
    tenant, user = _aligned()
    tenant.update(mutate_tenant)
    user.update(mutate_user)

    checks = _evaluate(tenant, user)
    failures = [name for name, passed, _ in checks if not passed]
    assert broken_check in failures


def test_output_never_leaks_a_clerk_identifier() -> None:
    """Boolean equality evidence only -- raw identifiers stay in process."""
    tenant, user = _aligned()
    for _, _, detail in _evaluate(tenant, user):
        assert _ORG not in detail
        assert _CLERK_USER not in detail
