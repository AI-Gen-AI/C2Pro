"""
BOM aggregate-level validation rules.

Refers to Suite ID: TS-UD-PROC-BOM-002.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from uuid import UUID

from .models import BOMItem


class BOMValidationRules:
    """Validates cross-item consistency rules for BOM item collections."""

    def __init__(self, max_items_per_wbs: int = 25) -> None:
        self.max_items_per_wbs = max_items_per_wbs

    def validate(self, items: list[BOMItem]) -> list[str]:
        if not items:
            return []

        errors: list[str] = []

        codes = [item.item_code for item in items if item.item_code]
        duplicate_codes = [code for code, count in Counter(codes).items() if count > 1]
        for code in duplicate_codes:
            errors.append(f"duplicate item_code: {code}")

        for item in items:
            if not item.item_code or not item.item_code.strip():
                errors.append(f"item_code is required for item {item.id}")

        supplier_key_counter: Counter[tuple[str, str]] = Counter()
        for item in items:
            supplier = (item.supplier or "").strip().lower()
            name = item.item_name.strip().lower()
            if supplier and name:
                supplier_key_counter[(supplier, name)] += 1
        for (supplier, name), count in supplier_key_counter.items():
            if count > 1:
                errors.append(f"duplicate supplier item: {supplier}/{name}")

        currencies = {item.currency for item in items}
        if len(currencies) > 1:
            errors.append("mixed currencies in BOM list")

        for item in items:
            if item.wbs_item_id is None:
                errors.append(f"missing wbs_item_id for item {item.id}")

            if item.unit_price is not None and item.total_price is not None:
                expected = Decimal(str(item.unit_price)) * Decimal(str(item.quantity))
                if item.total_price != expected:
                    errors.append(f"total_price mismatch for item {item.id}")

            production = item.production_time_days or 0
            transit = item.transit_time_days or 0
            if item.lead_time_days is not None and item.lead_time_days < (production + transit):
                errors.append(f"lead_time_days is lower than production+transit for item {item.id}")

        items_by_wbs: defaultdict[UUID, int] = defaultdict(int)
        for item in items:
            if item.wbs_item_id is not None:
                items_by_wbs[item.wbs_item_id] += 1
        for wbs_id, count in items_by_wbs.items():
            if count > self.max_items_per_wbs:
                errors.append(f"too many BOM items for WBS {wbs_id}")

        return errors
