"""TS-UD-AI-COST-001: Unit tests for CostControllerService budget tracking and cost calculation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ai.cost_controller import BudgetExceededException, CostControllerService


def _mock_tenant(
    *,
    ai_budget_monthly: float = 100.0,
    ai_spend_current: float = 0.0,
    ai_spend_last_reset: datetime | None = None,
) -> MagicMock:
    tenant = MagicMock()
    tenant.ai_budget_monthly = ai_budget_monthly
    tenant.ai_spend_current = ai_spend_current
    tenant.ai_spend_last_reset = ai_spend_last_reset
    return tenant


class TestCalculateCost:
    """Unit tests for CostControllerService.calculate_cost — no DB needed."""

    def test_calculate_cost_sonnet(self) -> None:
        svc = CostControllerService(db=MagicMock(spec=AsyncSession))
        cost = svc.calculate_cost(model="claude-sonnet", input_tokens=1000, output_tokens=500)
        assert cost == pytest.approx(0.0105)

    def test_calculate_cost_haiku(self) -> None:
        svc = CostControllerService(db=MagicMock(spec=AsyncSession))
        cost = svc.calculate_cost(model="claude-haiku", input_tokens=1000, output_tokens=500)
        assert cost == pytest.approx(0.000875)

    def test_calculate_cost_unknown_fallback(self) -> None:
        svc = CostControllerService(db=MagicMock(spec=AsyncSession))
        cost = svc.calculate_cost(model="gpt4", input_tokens=1000, output_tokens=500)
        assert cost == pytest.approx(0.0105)


class TestTrackUsage:
    """Unit tests for CostControllerService.track_usage with mocked get_tenant_by_id."""

    @pytest.mark.asyncio
    async def test_track_usage_adds_cost(self) -> None:
        tenant = _mock_tenant(ai_spend_current=5.0)
        db = MagicMock(spec=AsyncSession)
        db.commit = AsyncMock()

        with patch("src.core.ai.cost_controller.get_tenant_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = tenant
            svc = CostControllerService(db=db)
            await svc.track_usage(tenant_id=uuid4(), actual_cost=2.5)

            assert tenant.ai_spend_current == 7.5
            db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_track_usage_tenant_not_found(self) -> None:
        db = MagicMock(spec=AsyncSession)

        with patch("src.core.ai.cost_controller.get_tenant_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            svc = CostControllerService(db=db)
            await svc.track_usage(tenant_id=uuid4(), actual_cost=2.5)

            db.commit.assert_not_awaited()


class TestCheckBudgetAvailability:
    """Unit tests for CostControllerService.check_budget_availability."""

    @pytest.mark.asyncio
    async def test_tenant_not_found_raises(self) -> None:
        db = MagicMock(spec=AsyncSession)

        with patch("src.core.ai.cost_controller.get_tenant_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            svc = CostControllerService(db=db)

            with pytest.raises(BudgetExceededException, match="not found"):
                await svc.check_budget_availability(tenant_id=uuid4(), estimated_cost=1.0)

    @pytest.mark.asyncio
    async def test_budget_exceeded_raises(self) -> None:
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        tenant = _mock_tenant(ai_budget_monthly=10.0, ai_spend_current=9.0, ai_spend_last_reset=now_naive)
        db = MagicMock(spec=AsyncSession)

        with patch("src.core.ai.cost_controller.get_tenant_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = tenant
            svc = CostControllerService(db=db)

            with pytest.raises(BudgetExceededException, match="would exceed the monthly budget"):
                await svc.check_budget_availability(tenant_id=uuid4(), estimated_cost=2.0)

    @pytest.mark.asyncio
    async def test_budget_within_limit_passes(self) -> None:
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        tenant = _mock_tenant(ai_budget_monthly=100.0, ai_spend_current=5.0, ai_spend_last_reset=now_naive)
        db = MagicMock(spec=AsyncSession)

        with patch("src.core.ai.cost_controller.get_tenant_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = tenant
            svc = CostControllerService(db=db)
            await svc.check_budget_availability(tenant_id=uuid4(), estimated_cost=10.0)

    @pytest.mark.asyncio
    async def test_monthly_reset_when_no_prior_reset(self) -> None:
        tenant = _mock_tenant(ai_budget_monthly=100.0, ai_spend_current=50.0, ai_spend_last_reset=None)
        db = MagicMock(spec=AsyncSession)

        with patch("src.core.ai.cost_controller.get_tenant_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = tenant
            svc = CostControllerService(db=db)
            await svc.check_budget_availability(tenant_id=uuid4(), estimated_cost=10.0)

            assert tenant.ai_spend_current == 0.0
            assert tenant.ai_spend_last_reset is not None
