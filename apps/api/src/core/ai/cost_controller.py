from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.service import get_tenant_by_id

logger = structlog.get_logger()


def _utcnow_naive() -> datetime:
    """TS-UD-AI-COST-001: return UTC now for legacy TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class BudgetExceededException(Exception):
    """Raised when a tenant's budget is exceeded."""

    def __init__(self, message: str = "Budget exceeded for this tenant.") -> None:
        super().__init__(message)


# Prices per million tokens
CLAUDE_3_5_SONNET_INPUT = 3.00
CLAUDE_3_5_SONNET_OUTPUT = 15.00
CLAUDE_3_HAIKU_INPUT = 0.25
CLAUDE_3_HAIKU_OUTPUT = 1.25


class CostControllerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_budget_availability(self, tenant_id: UUID, estimated_cost: float) -> None:
        """
        Checks if a tenant has enough budget for an operation.
        """
        tenant = await get_tenant_by_id(self.db, tenant_id, lock_for_update=True)
        if not tenant:
            raise BudgetExceededException(
                f"Tenant {tenant_id} not found or has no budget configured."
            )

        # Reset monthly budget if needed.
        now = _utcnow_naive()
        if tenant.ai_spend_last_reset is None or (
            now.year > tenant.ai_spend_last_reset.year
            or now.month > tenant.ai_spend_last_reset.month
        ):
            tenant.ai_spend_current = 0.0
            tenant.ai_spend_last_reset = now
            logger.info("ai_budget_reset", tenant_id=str(tenant_id))

        # Pending N4 reservations are also liabilities. Without this check,
        # legacy calls could pass preflight by ignoring N4's in-flight spend.
        # Legacy callers still need their own atomic reservation protocol;
        # this check alone does not guarantee two legacy workers cannot race.
        raw_reserved = getattr(tenant, "ai_spend_reserved_usd", 0)
        reserved = (
            float(raw_reserved)
            if isinstance(raw_reserved, (int, float, Decimal))
            else 0.0
        )
        if reserved < 0:
            raise BudgetExceededException("Invalid tenant pending usage")
        if tenant.ai_spend_current + reserved + estimated_cost > tenant.ai_budget_monthly:
            logger.critical(
                "ai_budget_exceeded",
                tenant_id=str(tenant_id),
                current_spend=tenant.ai_spend_current,
                reserved_spend=reserved,
                estimated_cost=estimated_cost,
                budget=tenant.ai_budget_monthly,
            )
            raise BudgetExceededException(
                f"Operation blocked for tenant {tenant_id}. Estimated cost of ${estimated_cost:.4f} "
                f"would exceed the monthly budget of ${tenant.ai_budget_monthly:.2f}. "
                f"Current spend: ${tenant.ai_spend_current:.4f}."
            )

        usage_percent = (
            (tenant.ai_spend_current + reserved) / tenant.ai_budget_monthly * 100
            if tenant.ai_budget_monthly > 0 else 100.0
        )
        if usage_percent >= 90:
            logger.critical(
                "ai_budget_alert",
                tenant_id=str(tenant_id),
                usage_percent=usage_percent,
                level="90%",
            )
        elif usage_percent >= 75:
            logger.warning(
                "ai_budget_alert",
                tenant_id=str(tenant_id),
                usage_percent=usage_percent,
                level="75%",
            )
        elif usage_percent >= 50:
            logger.warning(
                "ai_budget_alert",
                tenant_id=str(tenant_id),
                usage_percent=usage_percent,
                level="50%",
            )

    async def track_usage(self, tenant_id: UUID, actual_cost: float) -> None:
        """Track legacy usage under a tenant-row lock to prevent lost updates."""
        tenant = await get_tenant_by_id(
            self.db, tenant_id, lock_for_update=True,
        )
        if not tenant:
            logger.error("track_usage_failed_tenant_not_found", tenant_id=str(tenant_id))
            return

        tenant.ai_spend_current += actual_cost
        # AsyncSession defaults to expire_on_commit; accessing ORM attributes
        # afterward may trigger an implicit async fetch (MissingGreenlet).
        new_total_spend = tenant.ai_spend_current
        await self.db.commit()
        logger.info(
            "ai_usage_tracked",
            tenant_id=str(tenant_id),
            cost_added=actual_cost,
            new_total_spend=new_total_spend,
        )

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculates the cost of an AI operation based on the model and token usage.
        """
        model_key = model.lower()
        if "sonnet" in model_key:
            input_price_per_million = CLAUDE_3_5_SONNET_INPUT
            output_price_per_million = CLAUDE_3_5_SONNET_OUTPUT
        elif "haiku" in model_key:
            input_price_per_million = CLAUDE_3_HAIKU_INPUT
            output_price_per_million = CLAUDE_3_HAIKU_OUTPUT
        else:
            input_price_per_million = CLAUDE_3_5_SONNET_INPUT
            output_price_per_million = CLAUDE_3_5_SONNET_OUTPUT
            logger.warning("ai_model_pricing_fallback", model=model)

        input_cost = (input_tokens / 1_000_000) * input_price_per_million
        output_cost = (output_tokens / 1_000_000) * output_price_per_million
        return input_cost + output_cost
