"""No-DB negative checks and amount semantics for issue #1274."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.admin.adapters.http.platform_budget_router import _item, _safe_search, budget_owner_only
from src.core.auth.platform_operator import PlatformOperator


def owner() -> PlatformOperator:
    return PlatformOperator(clerk_user_id="user_platform_owner", clerk_org_id="org_platform", email=None)


def test_only_explicit_single_owner_allowlist() -> None:
    for ids in ([], ["user_other"], ["user_platform_owner", "user_other"]):
        with patch("src.admin.adapters.http.platform_budget_router.settings",
                   SimpleNamespace(platform_operator_user_ids=ids)):
            with pytest.raises(HTTPException) as err:
                budget_owner_only(owner())
            assert err.value.status_code == 403
    with patch("src.admin.adapters.http.platform_budget_router.settings",
               SimpleNamespace(platform_operator_user_ids=["user_platform_owner"])):
        assert budget_owner_only(owner()).clerk_user_id == "user_platform_owner"


def test_owner_check_does_not_use_tenant_admin_role() -> None:
    with patch("src.admin.adapters.http.platform_budget_router.settings",
               SimpleNamespace(platform_operator_user_ids=["user_platform_owner"])):
        with pytest.raises(HTTPException) as err:
            budget_owner_only(PlatformOperator(
                clerk_user_id="user_customer_admin", clerk_org_id="org_platform", email=None
            ))
        assert err.value.status_code == 403


def test_literal_search_escapes_user_wildcards() -> None:
    assert _safe_search("acme%_\\") == "%acme\\%\\_\\\\%"
    assert _safe_search("") == "%%"


def test_no_double_counting_of_tenant_and_bucket_counters() -> None:
    row = {
        "tenant_id": "tenant-a", "name": "Acme", "slug": "acme", "is_active": True,
        "owner_cap": Decimal("5"), "bucket_cap": Decimal("5"),
        "tenant_spent": Decimal("1"), "bucket_spent": Decimal("1"),
        "tenant_reserved": Decimal("2"), "bucket_reserved": Decimal("2"),
        "updated_at": None,
    }
    result = _item(row)
    assert result.available_usd == Decimal("2.000000")
    assert result.utilisation_percent == Decimal("60.00")
    assert result.budget_status == "RECONCILED"
    row["bucket_cap"] = Decimal("3")
    assert _item(row).available_usd == 0
    row["bucket_reserved"] = Decimal("2.5")
    assert _item(row).budget_status == "COUNTERS_DIVERGED"
    row["bucket_cap"] = None
    assert _item(row).budget_status == "NO_TENANT_BUCKET"
