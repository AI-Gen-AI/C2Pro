"""
I8 - WBS/BOM Domain Generation Integrity
Test Suite ID: TS-I8-WBS-BOM-DOM-001
"""

from uuid import uuid4

from src.modules.wbs_bom.domain.entities import BOMItem, WBSItem
from src.modules.wbs_bom.domain.services import WBSBOMIntegrityService


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
