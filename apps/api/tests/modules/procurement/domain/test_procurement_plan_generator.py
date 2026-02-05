"""
Procurement plan generation tests.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from src.procurement.domain.models import BOMItem
from src.procurement.domain.procurement_plan_generator import (
    ProcurementPlanGenerator,
    ProcurementPriority,
)


class TestProcurementPlanGenerator:
    """Refers to Suite ID: TS-UD-PROC-PLN-001"""

    def test_001_generate_plan_from_bom_items(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[self._make_item("Concrete", "100.00", "3", 7)],
            required_on_site_date=date(2026, 3, 1),
            current_date=date(2026, 2, 10),
        )

        assert len(plan.items) == 1
        assert plan.items[0].item_name == "Concrete"

    def test_002_total_budget_is_sum_of_items(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[
                self._make_item("Concrete", "100.00", "3", 7),
                self._make_item("Steel", "50.00", "2", 4),
            ],
            required_on_site_date=date(2026, 3, 1),
            current_date=date(2026, 2, 10),
        )

        assert plan.total_cost == Decimal("400.00")

    def test_003_items_sorted_by_optimal_order_date(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[
                self._make_item("Long Lead", "10.00", "1", 10),
                self._make_item("Short Lead", "10.00", "1", 2),
            ],
            required_on_site_date=date(2026, 3, 1),
            current_date=date(2026, 2, 10),
        )

        assert plan.items[0].item_name == "Long Lead"
        assert plan.items[1].item_name == "Short Lead"

    def test_004_critical_priority_when_date_passed(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[self._make_item("Delayed", "10.00", "1", 10)],
            required_on_site_date=date(2026, 2, 10),
            current_date=date(2026, 2, 11),
        )

        assert plan.items[0].priority == ProcurementPriority.CRITICAL

    def test_005_high_priority_on_tight_margin(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[self._make_item("Tight", "10.00", "1", 5)],
            required_on_site_date=date(2026, 2, 15),
            current_date=date(2026, 2, 10),
        )

        assert plan.items[0].priority == ProcurementPriority.HIGH

    def test_006_medium_priority_on_watch_window(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[self._make_item("Watch", "10.00", "1", 6)],
            required_on_site_date=date(2026, 2, 20),
            current_date=date(2026, 2, 10),
        )

        assert plan.items[0].priority == ProcurementPriority.MEDIUM

    def test_007_low_priority_when_no_alerts(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[self._make_item("Safe", "10.00", "1", 3)],
            required_on_site_date=date(2026, 3, 10),
            current_date=date(2026, 2, 10),
        )

        assert plan.items[0].priority == ProcurementPriority.LOW

    def test_008_plan_includes_optimal_order_dates(self) -> None:
        generator = ProcurementPlanGenerator()
        required_on_site = date(2026, 3, 1)

        plan = generator.generate(
            bom_items=[self._make_item("Concrete", "10.00", "1", 7)],
            required_on_site_date=required_on_site,
            current_date=date(2026, 2, 1),
        )

        assert plan.items[0].optimal_order_date == date(2026, 2, 22)

    def test_009_plan_exposes_required_on_site_date(self) -> None:
        generator = ProcurementPlanGenerator()
        required_on_site = date(2026, 3, 1)

        plan = generator.generate(
            bom_items=[self._make_item("Concrete", "10.00", "1", 7)],
            required_on_site_date=required_on_site,
            current_date=date(2026, 2, 1),
        )

        assert plan.required_on_site_date == required_on_site

    def test_010_plan_item_alerts_are_propagated(self) -> None:
        generator = ProcurementPlanGenerator()

        plan = generator.generate(
            bom_items=[self._make_item("Delayed", "10.00", "1", 10)],
            required_on_site_date=date(2026, 2, 10),
            current_date=date(2026, 2, 11),
        )

        assert len(plan.items[0].alerts) == 1
        assert plan.items[0].alerts[0].code.value == "R14_DATE_PASSED"

    @staticmethod
    def _make_item(name: str, unit_price: str, quantity: str, lead_time_days: int) -> BOMItem:
        return BOMItem(
            project_id=UUID("11111111-1111-1111-1111-111111111111"),
            item_name=name,
            quantity=Decimal(quantity),
            unit_price=Decimal(unit_price),
            lead_time_days=lead_time_days,
        )
