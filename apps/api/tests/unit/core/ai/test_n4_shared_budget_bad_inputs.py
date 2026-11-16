"""Guard against negative/infinite charge amounts on legacy financial paths."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.core.ai.cost_controller import BudgetExceededException, CostControllerService
from src.core.tenants.schemas import AiSpendUpdate
from src.core.tenants.service import TenantService


@pytest.mark.parametrize("invalid", [-0.01, float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_legacy_budget_check_refuses_invalid_estimates(invalid):
    service = CostControllerService(db=MagicMock())
    with pytest.raises(BudgetExceededException, match="Invalid"):
        await service.check_budget_availability(uuid4(), invalid)


@pytest.mark.parametrize("invalid", [-0.01, float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_legacy_usage_tracking_refuses_invalid_charge(invalid):
    db = MagicMock()
    db.commit = AsyncMock()
    service = CostControllerService(db=db)
    with pytest.raises(BudgetExceededException, match="Invalid"):
        await service.track_usage(uuid4(), invalid)
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("invalid", [-0.01, float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_tenant_service_refuses_negative_or_nonfinite_spend(invalid):
    service = TenantService(db=MagicMock())
    with pytest.raises(ValueError, match="finite and nonnegative"):
        await service.update_ai_spend(uuid4(), invalid)


@pytest.mark.parametrize("invalid", [-0.01, float("nan"), float("inf"), float("-inf")])
def test_http_budget_schema_rejects_negative_or_nonfinite_spend(invalid):
    with pytest.raises(ValidationError):
        AiSpendUpdate(amount=invalid)
