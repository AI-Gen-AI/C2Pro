"""
BOM item entity tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PROC-BOM-001.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.procurement.domain.models import BOMCategory, BOMItem, ProcurementStatus


class TestBOMItemEntity:
    """Refers to Suite ID: TS-UD-PROC-BOM-001"""

    def test_001_bom_item_creation_all_fields(self) -> None:
        item = BOMItem(
            project_id=uuid4(),
            item_name="Steel Beam",
            quantity=Decimal("10"),
            wbs_item_id=uuid4(),
            item_code="BOM-001",
            description="Structural steel",
            category=BOMCategory.MATERIAL,
            unit="pcs",
            unit_price=Decimal("120.50"),
            currency="USD",
            supplier="ACME",
            lead_time_days=21,
            production_time_days=14,
            transit_time_days=7,
            incoterm="FOB",
            contract_clause_id=uuid4(),
            budget_item_id=uuid4(),
            procurement_status=ProcurementStatus.REQUESTED,
            bom_metadata={"source": "manual"},
        )
        assert item.item_name == "Steel Beam"
        assert item.total_price == Decimal("1205.00")

    def test_002_bom_item_creation_minimum_fields(self) -> None:
        item = BOMItem(
            project_id=uuid4(),
            item_name="Concrete",
            quantity=Decimal("1"),
        )
        assert item.currency == "EUR"
        assert item.procurement_status == ProcurementStatus.PENDING

    def test_003_bom_item_fails_without_item_name(self) -> None:
        with pytest.raises(ValueError, match="item_name is required"):
            BOMItem(project_id=uuid4(), item_name="", quantity=Decimal("1"))

    def test_004_bom_item_fails_without_project_id(self) -> None:
        with pytest.raises(ValueError, match="project_id is required"):
            BOMItem(project_id=None, item_name="Cement", quantity=Decimal("1"))

    def test_005_bom_item_fails_quantity_zero(self) -> None:
        with pytest.raises(ValueError, match="quantity must be > 0"):
            BOMItem(project_id=uuid4(), item_name="Cement", quantity=Decimal("0"))

    def test_006_bom_item_fails_quantity_negative(self) -> None:
        with pytest.raises(ValueError, match="quantity must be > 0"):
            BOMItem(project_id=uuid4(), item_name="Cement", quantity=Decimal("-1"))

    def test_007_bom_item_fails_unit_price_negative(self) -> None:
        with pytest.raises(ValueError, match="unit_price must be >= 0"):
            BOMItem(
                project_id=uuid4(),
                item_name="Cement",
                quantity=Decimal("1"),
                unit_price=Decimal("-0.01"),
            )

    def test_008_bom_item_total_price_autocalculated(self) -> None:
        item = BOMItem(
            project_id=uuid4(),
            item_name="Cable",
            quantity=Decimal("3"),
            unit_price=Decimal("15.00"),
        )
        assert item.total_price == Decimal("45.00")

    def test_009_bom_item_total_cost_prefers_total_price(self) -> None:
        item = BOMItem(
            project_id=uuid4(),
            item_name="Cable",
            quantity=Decimal("3"),
            unit_price=Decimal("15.00"),
            total_price=Decimal("40.00"),
        )
        assert item.get_total_cost() == Decimal("40.00")

    def test_010_bom_item_currency_must_be_three_uppercase_letters(self) -> None:
        with pytest.raises(ValueError, match="currency must be 3 uppercase letters"):
            BOMItem(
                project_id=uuid4(),
                item_name="Cable",
                quantity=Decimal("1"),
                currency="usd",
            )

    def test_011_bom_item_lead_time_autocalculated_from_components(self) -> None:
        item = BOMItem(
            project_id=uuid4(),
            item_name="Generator",
            quantity=Decimal("1"),
            production_time_days=10,
            transit_time_days=5,
        )
        assert item.lead_time_days == 15

    def test_012_bom_item_lead_time_component_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="time component must be >= 0"):
            BOMItem(
                project_id=uuid4(),
                item_name="Generator",
                quantity=Decimal("1"),
                production_time_days=-1,
            )

    def test_013_bom_item_procurement_status_updates(self) -> None:
        item = BOMItem(project_id=uuid4(), item_name="Valve", quantity=Decimal("1"))
        item.update_status(ProcurementStatus.ORDERED)
        assert item.procurement_status == ProcurementStatus.ORDERED

    def test_014_bom_item_estimated_delivery_date_uses_lead_time(self) -> None:
        item = BOMItem(
            project_id=uuid4(),
            item_name="Valve",
            quantity=Decimal("1"),
            lead_time_days=10,
        )
        order_date = datetime(2026, 2, 5, 10, 0, 0)
        assert item.get_estimated_delivery_date(order_date).date().isoformat() == "2026-02-15"
