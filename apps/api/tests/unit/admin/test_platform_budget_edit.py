"""#1274 phase 2: proposal validation and always-off runtime PATCH.
No database, no real tenant, no actual budget mutation.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.admin.adapters.http.platform_budget_router import (
    update_platform_budget_limit_disabled,
)
from src.admin.application.platform_budget_limit_service import (
    BudgetLimitConflict,
    BudgetLimitEditInput,
    validate_budget_limit,
)
from src.core.auth.platform_operator import PlatformOperator


def payload(*, expected: str = "5", new: str = "4") -> BudgetLimitEditInput:
    return BudgetLimitEditInput(
        tenant_id=UUID("00000000-0000-0000-0000-0000000000a1"),
        period_key="2026-11", expected_cap_usd=Decimal(expected),
        new_cap_usd=Decimal(new), reason="Reviewed budget adjustment",
        request_id=uuid4(), confirmed=True,
    )


def financial_check(request: BudgetLimitEditInput, **overrides: object) -> Decimal:
    fields: dict[str, object] = {
        "old_tenant_cap": "5", "old_bucket_cap": "5",
        "tenant_spent": "2", "bucket_spent": "2",
        "tenant_reserved": "1.5", "bucket_reserved": "1.5",
        "request": request, "owner_max_usd": Decimal("12"),
    }
    fields.update(overrides)
    return validate_budget_limit(**fields)


def test_current_cap_and_total_commitment_guard() -> None:
    assert financial_check(payload(new="3.5")) == Decimal("3.500000")
    with pytest.raises(BudgetLimitConflict, match="below spend"):
        financial_check(payload(new="3.49"))


def test_stale_cap_bucket_divergence_and_counter_divergence_all_rejected() -> None:
    with pytest.raises(BudgetLimitConflict, match="Stale"):
        financial_check(payload(expected="4"))
    with pytest.raises(BudgetLimitConflict, match="Stale"):
        financial_check(payload(), old_bucket_cap="4")
    with pytest.raises(BudgetLimitConflict, match="not reconciled"):
        financial_check(payload(), bucket_reserved="1.500001")
    with pytest.raises(BudgetLimitConflict, match="not reconciled"):
        financial_check(payload(), bucket_spent="2.000001")


def test_owner_policy_is_compulsory() -> None:
    with pytest.raises(BudgetLimitConflict, match="maximum"):
        financial_check(payload(new="12.000001"))


@pytest.mark.parametrize("cap", ["-1", "0", "NaN", "Infinity", "0.0000001"])
def test_invalid_cap_never_passes_schema(cap: str) -> None:
    with pytest.raises(ValidationError):
        payload(new=cap)


def test_reason_and_confirmation_required() -> None:
    source = payload().model_dump()
    for field, value in (("reason", "no"), ("confirmed", False)):
        invalid = dict(source)
        invalid[field] = value
        with pytest.raises(ValidationError):
            BudgetLimitEditInput.model_validate(invalid)


@pytest.mark.asyncio
async def test_runtime_patch_is_hard_disabled_even_for_operator() -> None:
    owner = PlatformOperator(
        clerk_user_id="user_fixture_owner", clerk_org_id="org_fixture", email=None
    )
    with pytest.raises(HTTPException) as denial:
        await update_platform_budget_limit_disabled(payload(), owner)
    assert denial.value.status_code == 503
    assert denial.value.detail == "Budget editing disabled pending security approval"
