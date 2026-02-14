"""
I8 WBS/BOM Domain Integrity Service
Test Suite ID: TS-I8-WBS-BOM-DOM-001
"""

from src.modules.wbs_bom.domain.entities import BOMItem, WBSItem


class WBSBOMIntegrityService:
    """Validates hierarchy and traceability constraints for generated artifacts."""

    def validate_hierarchy(self, items: list[WBSItem]) -> list[str]:
        violations: list[str] = []
        by_id = {item.wbs_id: item for item in items}

        for item in items:
            if item.level == 1:
                continue

            if not item.parent_wbs_id:
                violations.append(
                    f"WBS item {item.code} at level {item.level} is missing parent reference."
                )
                continue

            parent = by_id.get(item.parent_wbs_id)
            if not parent:
                violations.append(f"WBS item {item.code} references missing parent node.")
                continue

            if item.level != parent.level + 1:
                violations.append(
                    f"WBS item {item.code} has invalid level progression from parent {parent.code}."
                )

        return violations

    def validate_traceability(
        self,
        wbs_items: list[WBSItem],
        bom_items: list[BOMItem],
    ) -> list[str]:
        violations: list[str] = []
        wbs_ids = {item.wbs_id for item in wbs_items}

        for wbs_item in wbs_items:
            if wbs_item.clause_id is None:
                violations.append(f"WBS item {wbs_item.code} is missing clause traceability.")

        for bom_item in bom_items:
            if bom_item.clause_id is None:
                violations.append(f"BOM item {bom_item.description} is missing clause traceability.")
            if bom_item.wbs_id not in wbs_ids:
                violations.append(
                    f"BOM item {bom_item.description} references missing WBS {bom_item.wbs_id}."
                )

        return violations

