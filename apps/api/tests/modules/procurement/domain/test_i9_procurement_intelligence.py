"""
I9 - Procurement Planning Intelligence (Domain)
Test Suite ID: TS-I9-PROC-DOM-001
"""

from datetime import date
from decimal import Decimal

from src.modules.procurement.domain.entities import ProcurementPlanItem
from src.modules.procurement.domain.services import ProcurementIntelligenceService

def test_i9_detects_schedule_procurement_conflicts_for_late_orders() -> None:
    """Refers to I9.1: conflict intelligence must flag late order dates with explicit reason codes."""
    service = ProcurementIntelligenceService()
    items = [
        ProcurementPlanItem(
            item_name="High Voltage Switchgear",
            required_on_site_date=date(2026, 7, 1),
            optimal_order_date=date(2026, 6, 25),
            total_cost=Decimal("150000.00"),
        )
    ]

    conflicts = service.detect_conflicts(items, current_date=date(2026, 6, 28))

    assert len(conflicts) > 0
    assert any(c.reason_code == "LATE_ORDER_WINDOW" for c in conflicts)
    assert any(c.impact in {"HIGH", "CRITICAL"} for c in conflicts)


def test_i9_planning_output_fingerprint_is_deterministic_for_same_inputs() -> None:
    """Refers to I9.3: deterministic planning outputs required for auditability and replay."""
    service = ProcurementIntelligenceService()
    items = [
        ProcurementPlanItem(
            item_name="Concrete C30",
            required_on_site_date=date(2026, 8, 15),
            optimal_order_date=date(2026, 7, 20),
            total_cost=Decimal("45000.00"),
        ),
        ProcurementPlanItem(
            item_name="Rebar B500",
            required_on_site_date=date(2026, 8, 15),
            optimal_order_date=date(2026, 7, 10),
            total_cost=Decimal("32000.00"),
        ),
    ]

    fp_a = service.generate_plan_fingerprint(items)
    fp_b = service.generate_plan_fingerprint(items)

    assert fp_a
    assert fp_a == fp_b
