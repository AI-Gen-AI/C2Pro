"""
WBS/BOM domain integrity services.

Refers to Test Suite IDs: TS-I8-WBS-BOM-DOM-001, TS-I8-WBS-BOM-APP-001.
"""

from __future__ import annotations

from src.modules.wbs_bom.domain.entities import BOMItem, WBSItem


class WBSBOMIntegrityService:
    """Validate traceability and hierarchy invariants for generated artifacts."""

    def validate_hierarchy(self, wbs_items: list[WBSItem]) -> list[str]:
        """Return hierarchy violations for malformed parent chains."""
        violations: list[str] = []
        existing_ids = {item.wbs_id for item in wbs_items}

        for item in wbs_items:
            expected_level = item.code.count(".") + 1
            if item.level != expected_level:
                violations.append(
                    f"WBS item {item.code} has invalid level {item.level}; expected {expected_level}."
                )
            if item.level > 1 and item.parent_wbs_id is None:
                violations.append(f"WBS item {item.code} is missing parent reference.")
            if item.parent_wbs_id is not None and item.parent_wbs_id not in existing_ids:
                violations.append(f"WBS item {item.code} references missing parent node.")

        return violations

    def validate_traceability(
        self,
        wbs_items: list[WBSItem],
        bom_items: list[BOMItem],
    ) -> list[str]:
        """Return traceability violations for generated WBS/BOM artifacts."""
        violations: list[str] = []
        for item in wbs_items:
            if item.clause_id is None:
                violations.append(f"WBS item {item.code} is missing clause traceability.")
        for bom_item in bom_items:
            if bom_item.clause_id is None:
                violations.append(f"BOM item {bom_item.description} is missing clause traceability.")
        return violations
