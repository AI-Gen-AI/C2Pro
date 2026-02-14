"""
I8 - WBS/BOM Domain Generation Integrity
Test Suite ID: TS-I8-WBS-BOM-DOM-001
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

try:
    from src.modules.wbs_bom.domain.entities import WBSItem, BOMItem
    from src.modules.wbs_bom.domain.services import WBSBOMIntegrityService
except ImportError:
    @dataclass
    class WBSItem:  # type: ignore[override]
        wbs_id: UUID
        code: str
        name: str
        level: int
        clause_id: UUID | None = None
        parent_wbs_id: UUID | None = None

    @dataclass
    class BOMItem:  # type: ignore[override]
        bom_id: UUID
        wbs_id: UUID
        description: str
        quantity: float
        unit_cost: float
        clause_id: UUID | None = None

    class WBSBOMIntegrityService:  # type: ignore[override]
        def validate_hierarchy(self, items: list[WBSItem]) -> list[str]:
            return []

        def validate_traceability(self, wbs_items: list[WBSItem], bom_items: list[BOMItem]) -> list[str]:
            return []


def test_i8_wbs_hierarchy_constraints_require_valid_parent_chain() -> None:
    """Refers to I8: child WBS levels must have valid parent nodes and level progression."""
    root = WBSItem(wbs_id=uuid4(), code="1", name="Root", level=1, clause_id=uuid4())
    invalid_child = WBSItem(
        wbs_id=uuid4(),
        code="1.1.1",
        name="Invalid Child",
        level=3,
        clause_id=uuid4(),
        parent_wbs_id=None,
    )

    service = WBSBOMIntegrityService()
    violations = service.validate_hierarchy([root, invalid_child])

    assert len(violations) > 0
    assert any("parent" in v.lower() for v in violations)


def test_i8_clause_traceability_is_required_for_wbs_and_bom_items() -> None:
    """Refers to I8: generated WBS/BOM artifacts must preserve clause traceability links."""
    wbs_item = WBSItem(
        wbs_id=uuid4(),
        code="1.1",
        name="Concrete Works",
        level=2,
        clause_id=None,
        parent_wbs_id=uuid4(),
    )
    bom_item = BOMItem(
        bom_id=uuid4(),
        wbs_id=wbs_item.wbs_id,
        description="Concrete C30",
        quantity=120.0,
        unit_cost=95.0,
        clause_id=None,
    )

    service = WBSBOMIntegrityService()
    violations = service.validate_traceability([wbs_item], [bom_item])

    assert len(violations) >= 2
    assert any("clause" in v.lower() for v in violations)
