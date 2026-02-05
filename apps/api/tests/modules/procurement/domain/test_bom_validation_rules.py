"""
BOM validation rules tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PROC-BOM-002.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from src.procurement.domain.bom_validation_rules import BOMValidationRules
from src.procurement.domain.models import BOMItem


def _bom(**overrides) -> BOMItem:
    base = {
        "project_id": uuid4(),
        "item_name": "Cable Tray",
        "quantity": Decimal("2"),
        "item_code": "BOM-001",
        "unit_price": Decimal("10"),
        "currency": "USD",
        "wbs_item_id": uuid4(),
        "supplier": "ACME",
        "production_time_days": 4,
        "transit_time_days": 3,
        "lead_time_days": 7,
    }
    base.update(overrides)
    return BOMItem(**base)


class TestBOMValidationRules:
    """Refers to Suite ID: TS-UD-PROC-BOM-002"""

    def test_001_valid_bom_list_has_no_errors(self) -> None:
        item_a = _bom(item_code="BOM-001", item_name="Cable Tray")
        item_b = _bom(item_code="BOM-002", item_name="Conduit")
        rules = BOMValidationRules()

        errors = rules.validate([item_a, item_b])

        assert errors == []

    def test_002_duplicate_item_code_rejected(self) -> None:
        item_a = _bom(item_code="BOM-001")
        item_b = _bom(item_code="BOM-001", item_name="Conduit")

        errors = BOMValidationRules().validate([item_a, item_b])

        assert any("duplicate item_code" in error for error in errors)

    def test_003_duplicate_name_same_supplier_rejected(self) -> None:
        item_a = _bom(item_name="Cable Tray", supplier="ACME")
        item_b = _bom(item_code="BOM-002", item_name="Cable Tray", supplier="acme")

        errors = BOMValidationRules().validate([item_a, item_b])

        assert any("duplicate supplier item" in error for error in errors)

    def test_004_mixed_currencies_rejected(self) -> None:
        item_a = _bom(currency="USD")
        item_b = _bom(item_code="BOM-002", currency="EUR")

        errors = BOMValidationRules().validate([item_a, item_b])

        assert any("mixed currencies" in error for error in errors)

    def test_005_total_price_mismatch_rejected(self) -> None:
        item = _bom(total_price=Decimal("1"), quantity=Decimal("2"), unit_price=Decimal("10"))

        errors = BOMValidationRules().validate([item])

        assert any("total_price mismatch" in error for error in errors)

    def test_006_missing_wbs_link_rejected(self) -> None:
        item = _bom(wbs_item_id=None)

        errors = BOMValidationRules().validate([item])

        assert any("missing wbs_item_id" in error for error in errors)

    def test_007_lead_time_less_than_components_rejected(self) -> None:
        item = _bom(production_time_days=5, transit_time_days=5, lead_time_days=8)

        errors = BOMValidationRules().validate([item])

        assert any("lead_time_days is lower than production+transit" in error for error in errors)

    def test_008_too_many_items_per_wbs_rejected(self) -> None:
        wbs_id = uuid4()
        items = [
            _bom(item_code=f"BOM-00{i}", wbs_item_id=wbs_id, item_name=f"Item {i}")
            for i in range(1, 5)
        ]

        errors = BOMValidationRules(max_items_per_wbs=3).validate(items)

        assert any("too many BOM items for WBS" in error for error in errors)

    def test_009_empty_item_code_rejected(self) -> None:
        item = _bom(item_code="")

        errors = BOMValidationRules().validate([item])

        assert any("item_code is required" in error for error in errors)

    def test_010_empty_list_has_no_errors(self) -> None:
        assert BOMValidationRules().validate([]) == []
