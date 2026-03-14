"""
C2Pro - CostControllerService Unit Tests (Swarm)

Tests for the key logic in src/core/ai/cost_controller.py:

- check_budget_availability:
    1. tenant not found → raises BudgetExceededException
    2. ai_spend_last_reset is None OR date rolled over → resets ai_spend_current to 0.0
    3. current_spend + estimated_cost > monthly_budget → raises BudgetExceededException
    4. usage_percent >= 90 → critical log (allowed through)
    5. usage_percent >= 75 → warning log (allowed through)
    6. usage_percent >= 50 → warning log (allowed through)
    7. usage_percent < 50 → no threshold log (allowed through)

- track_usage:
    1. tenant not found → logs error, returns without raising
    2. tenant found → ai_spend_current incremented and db.commit() awaited

- calculate_cost:
    1. 'sonnet' in model → SONNET pricing
    2. 'haiku' in model → HAIKU pricing
    3. unknown model → falls back to SONNET pricing

Mocking strategy:
  - get_tenant_by_id is patched at 'src.core.ai.cost_controller.get_tenant_by_id'
  - AsyncSession is a MagicMock with commit = AsyncMock()
  - Tenant is a SimpleNamespace with ai_budget_monthly, ai_spend_current,
    ai_spend_last_reset attributes
"""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ai.cost_controller import (  # type: ignore[import]
    CLAUDE_3_5_SONNET_INPUT,
    CLAUDE_3_5_SONNET_OUTPUT,
    CLAUDE_3_HAIKU_INPUT,
    CLAUDE_3_HAIKU_OUTPUT,
    BudgetExceededException,
    CostControllerService,
)

# ---------------------------------------------------------------------------
# Module-level path for the dependency we always patch
# ---------------------------------------------------------------------------
_GET_TENANT_PATH = "src.core.ai.cost_controller.get_tenant_by_id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> MagicMock:
    """Return a minimal async-session mock."""
    db = MagicMock()
    db.commit = AsyncMock()
    return db


def _make_tenant(
    *,
    budget: float = 100.0,
    spend: float = 0.0,
    last_reset: datetime | None = None,
) -> SimpleNamespace:
    """Return a minimal Tenant-compatible object."""
    return SimpleNamespace(
        ai_budget_monthly=budget,
        ai_spend_current=spend,
        ai_spend_last_reset=last_reset,
    )


def _make_service(db: MagicMock | None = None) -> CostControllerService:
    """Instantiate CostControllerService with a mock db session."""
    return CostControllerService(db=db or _make_db())


# ===========================================================================
# TestCheckBudgetAvailability
# ===========================================================================


class TestCheckBudgetAvailability:
    """Unit tests for CostControllerService.check_budget_availability."""

    # ------------------------------------------------------------------
    # Tenant not found
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tenant_not_found_raises_budget_exceeded(self):
        """When get_tenant_by_id returns None, BudgetExceededException is raised."""
        service = _make_service()
        tenant_id = uuid.uuid4()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=None)):
            with pytest.raises(BudgetExceededException):
                await service.check_budget_availability(tenant_id, estimated_cost=0.01)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tenant_not_found_exception_message_contains_tenant_id(self):
        """BudgetExceededException message includes the tenant_id when tenant is missing."""
        service = _make_service()
        tenant_id = uuid.uuid4()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=None)):
            with pytest.raises(BudgetExceededException, match=str(tenant_id)):
                await service.check_budget_availability(tenant_id, estimated_cost=0.01)

    # ------------------------------------------------------------------
    # Monthly reset behaviour
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spend_reset_when_last_reset_is_none(self):
        """ai_spend_last_reset is None → ai_spend_current is zeroed before budget check."""
        tenant = _make_tenant(spend=50.0, last_reset=None)
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

        assert tenant.ai_spend_current == pytest.approx(0.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spend_reset_when_year_has_advanced(self):
        """Year > last_reset.year → ai_spend_current is zeroed."""
        last_reset = datetime(2024, 12, 1)
        tenant = _make_tenant(spend=40.0, last_reset=last_reset)
        service = _make_service()

        # Patch datetime.utcnow so it reports a future year
        future_now = datetime(2026, 1, 1)
        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            with patch("src.core.ai.cost_controller.datetime") as mock_dt:
                mock_dt.utcnow.return_value = future_now
                await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

        assert tenant.ai_spend_current == pytest.approx(0.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spend_reset_when_month_has_advanced(self):
        """Same year but month > last_reset.month → ai_spend_current is zeroed."""
        last_reset = datetime(2025, 3, 1)
        tenant = _make_tenant(spend=30.0, last_reset=last_reset)
        service = _make_service()

        same_year_next_month = datetime(2025, 4, 1)
        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            with patch("src.core.ai.cost_controller.datetime") as mock_dt:
                mock_dt.utcnow.return_value = same_year_next_month
                await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

        assert tenant.ai_spend_current == pytest.approx(0.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spend_not_reset_within_same_month(self):
        """Same year and same month → ai_spend_current is NOT zeroed."""
        now = datetime.utcnow()
        last_reset = datetime(now.year, now.month, 1)
        tenant = _make_tenant(spend=5.0, last_reset=last_reset)
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

        assert tenant.ai_spend_current == pytest.approx(5.0)

    # ------------------------------------------------------------------
    # Budget exceeded
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_raises_when_estimated_cost_exceeds_remaining_budget(self):
        """spend + estimated_cost > budget → BudgetExceededException raised."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=10.0,
            spend=9.99,
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            with pytest.raises(BudgetExceededException):
                await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.02)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_raises_when_estimated_cost_exactly_equals_remaining_budget_plus_epsilon(self):
        """spend + cost strictly > budget triggers the exception (not equal)."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=10.0,
            spend=9.0,
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            with pytest.raises(BudgetExceededException):
                await service.check_budget_availability(uuid.uuid4(), estimated_cost=1.01)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_does_not_raise_when_estimated_cost_within_budget(self):
        """spend + estimated_cost <= budget → no exception raised."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=100.0,
            spend=0.0,
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=50.0)
            # No exception expected

    # ------------------------------------------------------------------
    # Usage-percent warning thresholds (check does not raise)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_exception_when_usage_below_50_percent(self):
        """usage_percent < 50 → no exception, call completes normally."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=100.0,
            spend=10.0,  # 10% usage
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_exception_when_usage_at_50_percent(self):
        """usage_percent == 50 → warning threshold triggered but no exception."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=100.0,
            spend=50.0,
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_exception_when_usage_at_75_percent(self):
        """usage_percent == 75 → warning threshold triggered but no exception."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=100.0,
            spend=75.0,
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_exception_when_usage_at_90_percent(self):
        """usage_percent == 90 → critical threshold triggered but no exception."""
        now = datetime.utcnow()
        tenant = _make_tenant(
            budget=100.0,
            spend=90.0,
            last_reset=datetime(now.year, now.month, 1),
        )
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.check_budget_availability(uuid.uuid4(), estimated_cost=0.01)


# ===========================================================================
# TestTrackUsage
# ===========================================================================


class TestTrackUsage:
    """Unit tests for CostControllerService.track_usage."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tenant_not_found_returns_without_raising(self):
        """When get_tenant_by_id returns None, no exception is raised."""
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=None)):
            # Must complete without raising
            await service.track_usage(uuid.uuid4(), actual_cost=0.05)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tenant_not_found_does_not_commit(self):
        """When tenant is not found, db.commit() is NOT called."""
        db = _make_db()
        service = _make_service(db)

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=None)):
            await service.track_usage(uuid.uuid4(), actual_cost=0.05)

        db.commit.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tenant_found_increments_spend(self):
        """When tenant exists, ai_spend_current increases by actual_cost."""
        tenant = _make_tenant(spend=10.0)
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.track_usage(uuid.uuid4(), actual_cost=2.5)

        assert tenant.ai_spend_current == pytest.approx(12.5)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tenant_found_calls_db_commit(self):
        """When tenant exists, db.commit() is awaited."""
        db = _make_db()
        tenant = _make_tenant(spend=0.0)
        service = _make_service(db)

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.track_usage(uuid.uuid4(), actual_cost=1.0)

        db.commit.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_zero_cost_does_not_change_spend(self):
        """Tracking zero actual_cost leaves ai_spend_current unchanged."""
        tenant = _make_tenant(spend=5.0)
        service = _make_service()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.track_usage(uuid.uuid4(), actual_cost=0.0)

        assert tenant.ai_spend_current == pytest.approx(5.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_multiple_track_calls_accumulate_spend(self):
        """Successive track_usage calls keep incrementing the same tenant's spend."""
        tenant = _make_tenant(spend=0.0)
        service = _make_service()
        tenant_id = uuid.uuid4()

        with patch(_GET_TENANT_PATH, new=AsyncMock(return_value=tenant)):
            await service.track_usage(tenant_id, actual_cost=1.0)
            await service.track_usage(tenant_id, actual_cost=2.0)

        assert tenant.ai_spend_current == pytest.approx(3.0)


# ===========================================================================
# TestCalculateCost
# ===========================================================================


class TestCalculateCost:
    """Unit tests for CostControllerService.calculate_cost."""

    # ------------------------------------------------------------------
    # Sonnet pricing
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_sonnet_model_uses_sonnet_input_price(self):
        """Model name containing 'sonnet' applies SONNET input pricing."""
        service = _make_service()
        cost = service.calculate_cost("claude-3-5-sonnet-20241022", input_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(CLAUDE_3_5_SONNET_INPUT)

    @pytest.mark.unit
    def test_sonnet_model_uses_sonnet_output_price(self):
        """Model name containing 'sonnet' applies SONNET output pricing."""
        service = _make_service()
        cost = service.calculate_cost("claude-3-5-sonnet-20241022", input_tokens=0, output_tokens=1_000_000)
        assert cost == pytest.approx(CLAUDE_3_5_SONNET_OUTPUT)

    @pytest.mark.unit
    def test_sonnet_model_combined_cost(self):
        """Sonnet pricing: total = (input/1M)*INPUT_PRICE + (output/1M)*OUTPUT_PRICE."""
        service = _make_service()
        cost = service.calculate_cost(
            "claude-sonnet", input_tokens=500_000, output_tokens=100_000
        )
        expected = (500_000 / 1_000_000) * CLAUDE_3_5_SONNET_INPUT + (
            100_000 / 1_000_000
        ) * CLAUDE_3_5_SONNET_OUTPUT
        assert cost == pytest.approx(expected)

    @pytest.mark.unit
    def test_sonnet_matching_is_case_insensitive(self):
        """'SONNET' (uppercase) in model name triggers SONNET pricing."""
        service = _make_service()
        cost_lower = service.calculate_cost("claude-sonnet", input_tokens=1_000, output_tokens=1_000)
        cost_upper = service.calculate_cost("CLAUDE-SONNET", input_tokens=1_000, output_tokens=1_000)
        assert cost_lower == pytest.approx(cost_upper)

    # ------------------------------------------------------------------
    # Haiku pricing
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_haiku_model_uses_haiku_input_price(self):
        """Model name containing 'haiku' applies HAIKU input pricing."""
        service = _make_service()
        cost = service.calculate_cost("claude-3-haiku-20240307", input_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(CLAUDE_3_HAIKU_INPUT)

    @pytest.mark.unit
    def test_haiku_model_uses_haiku_output_price(self):
        """Model name containing 'haiku' applies HAIKU output pricing."""
        service = _make_service()
        cost = service.calculate_cost("claude-3-haiku-20240307", input_tokens=0, output_tokens=1_000_000)
        assert cost == pytest.approx(CLAUDE_3_HAIKU_OUTPUT)

    @pytest.mark.unit
    def test_haiku_model_combined_cost(self):
        """Haiku pricing: total = (input/1M)*HAIKU_INPUT + (output/1M)*HAIKU_OUTPUT."""
        service = _make_service()
        cost = service.calculate_cost(
            "claude-3-haiku-20240307", input_tokens=200_000, output_tokens=50_000
        )
        expected = (200_000 / 1_000_000) * CLAUDE_3_HAIKU_INPUT + (
            50_000 / 1_000_000
        ) * CLAUDE_3_HAIKU_OUTPUT
        assert cost == pytest.approx(expected)

    @pytest.mark.unit
    def test_haiku_cheaper_than_sonnet_for_same_tokens(self):
        """Haiku cost is always less than Sonnet cost for identical token counts."""
        service = _make_service()
        tokens = 100_000
        haiku_cost = service.calculate_cost("claude-haiku", input_tokens=tokens, output_tokens=tokens)
        sonnet_cost = service.calculate_cost("claude-sonnet", input_tokens=tokens, output_tokens=tokens)
        assert haiku_cost < sonnet_cost

    # ------------------------------------------------------------------
    # Unknown model falls back to Sonnet
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_unknown_model_falls_back_to_sonnet_pricing(self):
        """A model name containing neither 'sonnet' nor 'haiku' uses SONNET pricing."""
        service = _make_service()
        cost_unknown = service.calculate_cost(
            "gpt-4-turbo", input_tokens=1_000_000, output_tokens=0
        )
        assert cost_unknown == pytest.approx(CLAUDE_3_5_SONNET_INPUT)

    @pytest.mark.unit
    def test_unknown_model_output_falls_back_to_sonnet_output_pricing(self):
        """Unknown model output tokens are priced at SONNET output rate."""
        service = _make_service()
        cost_unknown = service.calculate_cost(
            "unknown-model-v1", input_tokens=0, output_tokens=1_000_000
        )
        assert cost_unknown == pytest.approx(CLAUDE_3_5_SONNET_OUTPUT)

    # ------------------------------------------------------------------
    # Zero tokens
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_zero_tokens_returns_zero_cost(self):
        """Zero input and output tokens → cost is 0.0 regardless of model."""
        service = _make_service()
        for model in ("claude-sonnet", "claude-haiku", "some-other-model"):
            assert service.calculate_cost(model, input_tokens=0, output_tokens=0) == pytest.approx(0.0)

    # ------------------------------------------------------------------
    # Pricing constant sanity checks
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_sonnet_pricing_constants_are_positive(self):
        """SONNET input and output prices are strictly positive."""
        assert CLAUDE_3_5_SONNET_INPUT > 0
        assert CLAUDE_3_5_SONNET_OUTPUT > 0

    @pytest.mark.unit
    def test_haiku_pricing_constants_are_positive(self):
        """HAIKU input and output prices are strictly positive."""
        assert CLAUDE_3_HAIKU_INPUT > 0
        assert CLAUDE_3_HAIKU_OUTPUT > 0

    @pytest.mark.unit
    def test_output_more_expensive_than_input_for_sonnet(self):
        """SONNET output price per million is higher than input price per million."""
        assert CLAUDE_3_5_SONNET_OUTPUT > CLAUDE_3_5_SONNET_INPUT

    @pytest.mark.unit
    def test_output_more_expensive_than_input_for_haiku(self):
        """HAIKU output price per million is higher than input price per million."""
        assert CLAUDE_3_HAIKU_OUTPUT > CLAUDE_3_HAIKU_INPUT
