"""
I9 Procurement Domain Services
Test Suite ID: TS-I9-PROC-DOM-001
"""

import hashlib
from datetime import date

from src.modules.procurement.domain.entities import ProcurementConflict, ProcurementPlanItem


class ProcurementIntelligenceService:
    """Deterministic planning intelligence for conflict detection and plan fingerprinting."""

    def detect_conflicts(
        self,
        items: list[ProcurementPlanItem],
        current_date: date,
    ) -> list[ProcurementConflict]:
        conflicts: list[ProcurementConflict] = []
        for item in items:
            if current_date > item.optimal_order_date:
                days_late = (current_date - item.optimal_order_date).days
                impact = "CRITICAL" if days_late >= 7 else "HIGH"
                conflicts.append(
                    ProcurementConflict(
                        item_id=item.item_id,
                        reason_code="LATE_ORDER_WINDOW",
                        impact=impact,
                        message=(
                            f"Order window missed by {days_late} day(s) for {item.item_name}. "
                            f"Required on site {item.required_on_site_date.isoformat()}."
                        ),
                    )
                )
        return conflicts

    def generate_plan_fingerprint(self, items: list[ProcurementPlanItem]) -> str:
        canonical_rows = [
            "|".join(
                [
                    item.item_name,
                    item.required_on_site_date.isoformat(),
                    item.optimal_order_date.isoformat(),
                    str(item.total_cost),
                ]
            )
            for item in items
        ]
        canonical_payload = "\n".join(sorted(canonical_rows))
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

