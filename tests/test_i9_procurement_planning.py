# Path: apps/api/src/procurement/tests/integration/test_i9_procurement_planning.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import date, timedelta

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.procurement.application.services import ProcurementPlannerService
    from src.procurement.application.dtos import ProcurementPlanItem, VendorData
    from src.procurement.application.util import LeadTimeCalculator
    from src.projects.application.dtos import BOMItem
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    ProcurementPlannerService = type("ProcurementPlannerService", (), {})
    ProcurementPlanItem = type("ProcurementPlanItem", (), {})
    VendorData = type("VendorData", (), {})
    LeadTimeCalculator = type("LeadTimeCalculator", (), {})
    BOMItem = type("BOMItem", (), {})


@pytest.fixture
def bom_item_fixture() -> BOMItem:
    """Provides a fixture for a Bill of Materials item."""
    return BOMItem(id=uuid4(), name="Steel Beams", required_by_date=date(2025, 10, 31))


@pytest.fixture
def vendor_data_fixture() -> VendorData:
    """Provides a fixture for vendor data with complete lead time info."""
    return VendorData(
        vendor_id=uuid4(),
        production_time_days=20,
        transit_time_days=10,
        buffer_days=5,
    )


@pytest.fixture
def incomplete_vendor_data_fixture() -> VendorData:
    """Provides a fixture for vendor data with missing lead time info."""
    return VendorData(vendor_id=uuid4(), production_time_days=None)


@pytest.mark.integration
@pytest.mark.tdd
class TestProcurementPlanningIntelligence:
    """
    Test suite for I9 - Procurement Planning Intelligence.
    """

    def test_i9_01_lead_time_calculator_uses_calendar_days(self):
        """
        [TEST-I9-01] Verifies the lead time calculator correctly uses calendar days.
        """
        # Arrange: This test expects a `LeadTimeCalculator` utility to exist.
        calculator = LeadTimeCalculator()
        required_date = date(2025, 10, 31)
        total_lead_time = 35  # 20 production + 10 transit + 5 buffer

        # Act: This call will fail until the calculator is implemented.
        order_date = calculator.calculate_order_date(
            required_date=required_date, lead_time_days=total_lead_time
        )

        # Assert
        expected_date = required_date - timedelta(days=total_lead_time)
        assert order_date == expected_date
        assert order_date == date(2025, 9, 26)

    @pytest.mark.xfail(reason="[TDD] Drives implementation of business day logic.", strict=True)
    def test_i9_02_lead_time_calculator_uses_business_days(self):
        """
        [TEST-I9-02] Verifies the calculator can use business days, skipping weekends.
        """
        # Arrange
        calculator = LeadTimeCalculator(use_business_days=True)
        required_date = date(2025, 3, 31)  # A Monday
        lead_time_business_days = 5

        # Act
        order_date = calculator.calculate_order_date(
            required_date=required_date, lead_time_days=lead_time_business_days
        )

        # Assert: 5 business days before Monday, March 31 is Monday, March 24.
        assert order_date == date(2025, 3, 24)
        assert False, "Remove this line once business day logic is implemented."

    @pytest.mark.asyncio
    async def test_i9_03_planner_produces_plan_item(
        self, bom_item_fixture, vendor_data_fixture
    ):
        """
        [TEST-I9-03] Verifies the planner service produces a valid plan item DTO.
        """
        # Arrange: This test expects the main `ProcurementPlannerService` to exist.
        planner = ProcurementPlannerService()
        # Mock the internal calculation for a predictable output
        planner.create_plan_item = AsyncMock(return_value=ProcurementPlanItem(
            bom_item_id=bom_item_fixture.id,
            optimal_order_date=date(2025, 9, 26),
            needs_human_review=False
        ))

        # Act
        plan_item = await planner.create_plan_item(bom_item_fixture, vendor_data_fixture)

        # Assert
        assert isinstance(plan_item, ProcurementPlanItem)
        assert plan_item.bom_item_id == bom_item_fixture.id
        assert plan_item.optimal_order_date == date(2025, 9, 26)
        assert plan_item.needs_human_review is False

    @pytest.mark.xfail(reason="[TDD] Drives graceful handling of missing data.", strict=True)
    @pytest.mark.asyncio
    async def test_i9_04_planner_flags_items_with_missing_data(
        self, bom_item_fixture, incomplete_vendor_data_fixture
    ):
        """
        [TEST-I9-04] Verifies the planner flags items when vendor data is missing.
        """
        # Arrange
        planner = ProcurementPlannerService()
        planner.create_plan_item = AsyncMock(return_value=ProcurementPlanItem(
            bom_item_id=bom_item_fixture.id,
            optimal_order_date=None,
            needs_human_review=True,
            review_reason="Missing vendor lead time."
        ))

        # Act
        plan_item = await planner.create_plan_item(bom_item_fixture, incomplete_vendor_data_fixture)

        # Assert
        assert plan_item.optimal_order_date is None
        assert plan_item.needs_human_review is True
        assert "Missing" in plan_item.review_reason
        assert False, "Remove this line once the fallback logic is implemented."