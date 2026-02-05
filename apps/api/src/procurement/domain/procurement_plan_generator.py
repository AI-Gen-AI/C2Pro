"""
Procurement plan generation domain service.

Refers to Suite ID: TS-UD-PROC-PLN-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from src.procurement.domain.lead_time_alerts import LeadTimeAlert, LeadTimeAlertEvaluator
from src.procurement.domain.lead_time_calculator import LeadTimeCalculator
from src.procurement.domain.models import BOMItem


class ProcurementPriority(str, Enum):
    """Priority for procurement execution order."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ProcurementPlanItem:
    """Line item in a generated procurement plan."""

    bom_item_id: UUID
    item_name: str
    quantity: Decimal
    total_cost: Decimal
    required_on_site_date: date
    optimal_order_date: date
    priority: ProcurementPriority
    alerts: list[LeadTimeAlert] = field(default_factory=list)


@dataclass(frozen=True)
class ProcurementPlan:
    """Procurement plan aggregate."""

    required_on_site_date: date
    items: list[ProcurementPlanItem]
    total_cost: Decimal


class ProcurementPlanGenerator:
    """Generates a procurement plan from BOM items and lead-time risk."""

    def __init__(self) -> None:
        self._lead_time_calculator = LeadTimeCalculator()
        self._alert_evaluator = LeadTimeAlertEvaluator()

    def generate(
        self,
        bom_items: list[BOMItem],
        required_on_site_date: date,
        current_date: date,
    ) -> ProcurementPlan:
        plan_items: list[ProcurementPlanItem] = []
        total_cost = Decimal("0")

        for item in bom_items:
            lead_days = item.lead_time_days or 0
            optimal_order_date = self._lead_time_calculator.calculate_optimal_order_date(
                required_on_site_date=required_on_site_date,
                production_days=lead_days,
            )
            alerts = self._alert_evaluator.evaluate(
                optimal_order_date=optimal_order_date,
                current_date=current_date,
            )
            priority = self._priority_from_alerts(alerts)
            item_total_cost = item.get_total_cost()
            total_cost += item_total_cost

            plan_items.append(
                ProcurementPlanItem(
                    bom_item_id=item.id,
                    item_name=item.item_name,
                    quantity=item.quantity,
                    total_cost=item_total_cost,
                    required_on_site_date=required_on_site_date,
                    optimal_order_date=optimal_order_date,
                    priority=priority,
                    alerts=alerts,
                )
            )

        plan_items.sort(key=lambda value: value.optimal_order_date)
        return ProcurementPlan(
            required_on_site_date=required_on_site_date,
            items=plan_items,
            total_cost=total_cost,
        )

    @staticmethod
    def _priority_from_alerts(alerts: list[LeadTimeAlert]) -> ProcurementPriority:
        if not alerts:
            return ProcurementPriority.LOW

        first = alerts[0]
        if first.severity.value == "critical":
            return ProcurementPriority.CRITICAL
        if first.severity.value == "warning":
            return ProcurementPriority.HIGH
        return ProcurementPriority.MEDIUM
