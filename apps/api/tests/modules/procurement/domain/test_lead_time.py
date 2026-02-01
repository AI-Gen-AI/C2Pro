"""
Lead Time Calculator Tests (TDD - RED Phase)

Refers to Suite ID: TS-UD-PROC-LTM-001.
"""

from __future__ import annotations

from datetime import date

from src.procurement.domain.lead_time_calculator import LeadTimeCalculator


class TestLeadTimeCalculator:
    """Refers to Suite ID: TS-UD-PROC-LTM-001."""

    def test_optimal_order_date_is_start_date_minus_lead_time(self):
        calculator = LeadTimeCalculator()
        start_date = date(2026, 2, 1)

        optimal = calculator.calculate_optimal_order_date(
            start_date=start_date,
            production_days=10,
            transit_days=5,
            customs_days=3,
            buffer_days=2,
        )

        assert optimal == date(2026, 1, 12)
