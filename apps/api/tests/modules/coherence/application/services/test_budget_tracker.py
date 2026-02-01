"""
Budget Tracking Service Tests (TDD - RED Phase)

Refers to Suite ID: TS-UA-SVC-BDG-001.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.coherence.application.services.budget_tracker import BudgetTrackerService


class TestBudgetTrackerService:
    """Refers to Suite ID: TS-UA-SVC-BDG-001."""

    def test_budget_throttle_at_95_percent(self):
        repo = MagicMock()
        repo.get_daily_spend_usd.return_value = 29.00

        service = BudgetTrackerService(cost_repository=repo, daily_limit_usd=30.00)

        result = service.check_budget(tenant_id="tenant-1")

        assert result["throttle"] is True
