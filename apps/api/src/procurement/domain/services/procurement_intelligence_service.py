"""
Procurement Intelligence Service.
Deterministic planning intelligence for conflict detection and plan fingerprinting.

Refers to Suite ID: TS-I9-PROC-DOM-001.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from src.procurement.domain.models import ProcurementConflict, ProcurementPlanItem


class ProcurementIntelligenceService:
    """Deterministic planning intelligence for conflict detection and plan fingerprinting."""

    def detect_conflicts(
        self,
        items: list[ProcurementPlanItem],
        current_date: date | datetime,
    ) -> list[ProcurementConflict]:
        conflicts: list[ProcurementConflict] = []
        
        # Ensure current_date is a date for comparison if items use date
        if isinstance(current_date, datetime):
            comp_date = current_date.date()
        else:
            comp_date = current_date

        for item in items:
            item_order_date = item.optimal_order_date
            if isinstance(item_order_date, datetime):
                item_order_date = item_order_date.date()
                
            if comp_date > item_order_date:
                days_late = (comp_date - item_order_date).days
                impact = "CRITICAL" if days_late >= 7 else "HIGH"
                
                required_date = item.required_on_site_date
                if hasattr(required_date, "isoformat"):
                    required_date_str = required_date.isoformat()
                else:
                    required_date_str = str(required_date)

                conflicts.append(
                    ProcurementConflict(
                        item_id=item.bom_item_id,
                        reason_code="LATE_ORDER_WINDOW",
                        impact=impact,
                        message=(
                            f"Order window missed by {days_late} day(s) for {item.item_name}. "
                            f"Required on site {required_date_str}."
                        ),
                    )
                )
        return conflicts

    def generate_plan_fingerprint(self, items: list[ProcurementPlanItem]) -> str:
        canonical_rows = []
        for item in items:
            required_date = item.required_on_site_date
            if hasattr(required_date, "isoformat"):
                required_date_str = required_date.isoformat()
            else:
                required_date_str = str(required_date)
                
            order_date = item.optimal_order_date
            if hasattr(order_date, "isoformat"):
                order_date_str = order_date.isoformat()
            else:
                order_date_str = str(order_date)

            canonical_rows.append(
                "|".join(
                    [
                        item.item_name,
                        required_date_str,
                        order_date_str,
                        str(item.total_cost),
                    ]
                )
            )
        canonical_payload = "\n".join(sorted(canonical_rows))
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
