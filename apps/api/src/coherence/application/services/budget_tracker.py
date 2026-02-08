"""
Budget tracking service.

Refers to Suite ID: TS-UA-SVC-BDG-001.
"""

from __future__ import annotations

from typing import Protocol


class _CostRepository(Protocol):
    def get_daily_spend_usd(self, tenant_id: str) -> float: ...


class BudgetTrackerService:
    """Refers to Suite ID: TS-UA-SVC-BDG-001."""

    def __init__(self, *, cost_repository: _CostRepository, daily_limit_usd: float) -> None:
        self.cost_repository = cost_repository
        self.daily_limit_usd = daily_limit_usd

    def check_budget(self, *, tenant_id: str) -> dict[str, bool]:
        spend = self.cost_repository.get_daily_spend_usd(tenant_id)
        throttle = spend >= (self.daily_limit_usd * 0.95)
        return {"throttle": throttle}
