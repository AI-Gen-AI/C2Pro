
import pytest
from datetime import date, timedelta
from typing import List, NamedTuple, Dict
from unittest.mock import MagicMock, AsyncMock
from enum import Enum, auto

# This import will fail as the modules do not exist yet.
from apps.api.src.procurement.domain.lead_time_calculator import (
    LeadTimeCalculator,
    CalendarService,
    LeadTimeComponents,
    LeadTimeResult,
    LeadTimeAlert,
    LeadTimeSeverity,
    LeadTimeStatus,
)

# --- Temporary definitions for test development ---
class TempLeadTimeSeverity(Enum):
    CRITICAL = auto()
    WARNING = auto()

class TempLeadTimeStatus(Enum):
    DATE_PASSED = auto()
    TIGHT_MARGIN = auto()
    OK = auto()

class TempLeadTimeAlert(NamedTuple):
    status: TempLeadTimeStatus
    severity: TempLeadTimeSeverity
    message: str

class TempLeadTimeComponents(NamedTuple):
    production_days: int = 0
    transit_days: int = 0
    buffer_days: int = 0

class TempLeadTimeResult(NamedTuple):
    optimal_required_on_site_date: date
    lead_time_breakdown: TempLeadTimeComponents
    alerts: List[TempLeadTimeAlert]


# --- Test Fixtures ---
@pytest.fixture
def mock_calendar_service() -> MagicMock:
    """
    Mock CalendarService to control working days and holidays.
    By default, it just adds the days, ignoring weekends/holidays unless specified.
    """
    mock = MagicMock(spec=CalendarService)
    # Default behavior: simply add days
    mock.add_business_days.side_effect = lambda start_date, days: start_date + timedelta(days=days)
    mock.is_working_day.return_value = True # Default to all days are working days
    return mock

@pytest.fixture
def calculator(mock_calendar_service: MagicMock) -> LeadTimeCalculator:
    """Provides an instance of the LeadTimeCalculator."""
    # Temporarily attach the temp classes for testing
    service = LeadTimeCalculator(calendar_service=mock_calendar_service)
    service.LeadTimeSeverity = TempLeadTimeSeverity
    service.LeadTimeStatus = TempLeadTimeStatus
    service.LeadTimeAlert = TempLeadTimeAlert
    service.LeadTimeComponents = TempLeadTimeComponents
    service.LeadTimeResult = TempLeadTimeResult
    return service

# --- Test Cases ---
@pytest.mark.asyncio
class TestLeadTimeCalculator:
    """Refers to Suite ID: TS-UD-PROC-LTM-001"""

    REQUIRED_BY_DATE = date(2024, 1, 31)

    # --- Optimal Date Calculation (test_001-004) ---
    @pytest.mark.parametrize("production, transit, buffer, expected_optimal_date_str", [
        (10, 0, 0, "2024-01-21"), # Production only
        (10, 5, 0, "2024-01-16"), # Production + Transit
        (10, 5, 3, "2024-01-13"), # All components
        (0, 0, 0, "2024-01-31"), # No lead time
    ])
    async def test_001_to_004_optimal_date_calculation(self, calculator, mock_calendar_service, production, transit, buffer, expected_optimal_date_str):
        components = calculator.LeadTimeComponents(production, transit, buffer)
        expected_date = date.fromisoformat(expected_optimal_date_str)
        
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        
        assert result.optimal_required_on_site_date == expected_date
        # Ensure add_business_days was called with the correct total lead time
        mock_calendar_service.add_business_days.assert_called_with(
            self.REQUIRED_BY_DATE, -(production + transit + buffer)
        )

    async def test_005_lead_time_breakdown_returned(self, calculator):
        """Tests that the lead time breakdown is returned in the result."""
        components = calculator.LeadTimeComponents(production_days=10, transit_days=5, buffer_days=2)
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        assert result.lead_time_breakdown == components

    async def test_006_required_on_site_calculation(self, calculator):
        """Confirm the final required_on_site_date is correct (same as optimal date tests)."""
        components = calculator.LeadTimeComponents(production_days=7, transit_days=3, buffer_days=0)
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        # Expected: Jan 31 - 10 days = Jan 21
        assert result.optimal_required_on_site_date == date(2024, 1, 21)

    # --- Calendar Exclusions (test_007-011) ---
    async def test_007_business_days_calculation(self, calculator, mock_calendar_service):
        """Tests that only business days are counted."""
        # Setup mock to simulate a calendar that skips weekends
        mock_calendar_service.add_business_days.side_effect = lambda start_date, days: start_date + timedelta(days=days + (2 * (abs(days) // 5))) if days < 0 else start_date + timedelta(days=days + (2 * (days // 5)))
        
        components = calculator.LeadTimeComponents(production_days=5) # 5 business days = 7 calendar days
        # Jan 31 (Wed) - 5 business days = Jan 24 (Wed)
        # Jan 31 - 2 business days = Jan 29
        # M W F T T
        # 31 30 29 28 27
        # ^ -1 -2 -3 -4 -5 = Jan 24
        
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        assert result.optimal_required_on_site_date == date(2024, 1, 24)

    async def test_008_weekend_exclusion(self, calculator, mock_calendar_service):
        """Tests that if a calculated date falls on a weekend, it's adjusted."""
        # Mock add_business_days to push dates from Jan 27-28 (weekend) to Jan 26 (Fri)
        mock_calendar_service.add_business_days.side_effect = None # Remove previous side_effect
        def custom_add_days(start_date: date, days: int) -> date:
            current = start_date
            if days < 0:
                for _ in range(abs(days)):
                    current -= timedelta(days=1)
                    while not (current.weekday() < 5): # skip Saturday (5) and Sunday (6)
                        current -= timedelta(days=1)
            return current
        mock_calendar_service.add_business_days.side_effect = custom_add_days
        
        # Required by Jan 31 (Wed). 3 days lead time means Jan 28 (Sun). Should adjust to Jan 26 (Fri).
        components = calculator.LeadTimeComponents(production_days=3)
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        assert result.optimal_required_on_site_date == date(2024, 1, 26) # Adjusted from Sun 28th

    async def test_009_holiday_exclusion(self, calculator, mock_calendar_service):
        """Tests that holidays are excluded from business day calculations."""
        # Jan 26, 2024 is a Friday. Let's make it a holiday.
        mock_calendar_service.is_working_day.side_effect = lambda d: d != date(2024, 1, 26) and d.weekday() < 5

        # Required by Jan 31 (Wed). 3 business days lead time.
        # Jan 31 (-1) Jan 30 (-2) Jan 29 (-3) Jan 26 (Holiday, skip) Jan 25
        # Expected: Jan 25
        components = calculator.LeadTimeComponents(production_days=3)
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        assert result.optimal_required_on_site_date == date(2024, 1, 25)

    async def test_010_delivery_on_weekend_adjusted(self, calculator, mock_calendar_service):
        """Tests that if the final calculated optimal date falls on a non-working day, it's adjusted to the next working day."""
        # For simplicity, mock the add_business_days to just subtract calendar days
        mock_calendar_service.add_business_days.side_effect = lambda start_date, days: start_date + timedelta(days=days)
        # Mock is_working_day to make Jan 28 (Sun) and Jan 29 (Mon) non-working days
        mock_calendar_service.is_working_day.side_effect = lambda d: d not in [date(2024, 1, 28), date(2024, 1, 29)]

        # Required by date: Jan 31 (Wed). Total lead time: 2 days.
        # Optimal date: Jan 29 (Mon). This is a mocked non-working day. Should adjust.
        # After adjustment: Jan 27 (Sat - weekend), Jan 26 (Fri - working).
        # Should actually be adjusted to the *previous* working day.
        components = calculator.LeadTimeComponents(production_days=2)
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        # Original: Jan 31 - 2 = Jan 29 (Non-working) -> Adjusted to Jan 26 (Fri)
        assert result.optimal_required_on_site_date == date(2024, 1, 26)

    async def test_011_mixed_calendar_business_days(self, calculator, mock_calendar_service):
        """Tests calculation considering both weekends and holidays."""
        # Jan 31 (Wed) - Jan 2024
        # Holidays: Jan 25 (Thu), Jan 26 (Fri)
        # Weekends: Jan 27 (Sat), Jan 28 (Sun)
        holidays = {date(2024, 1, 25), date(2024, 1, 26)}
        mock_calendar_service.is_working_day.side_effect = lambda d: d not in holidays and d.weekday() < 5
        
        # We need to test add_business_days more thoroughly here.
        # Add a custom side_effect for add_business_days for this complex test.
        def custom_add_business_days(start_date: date, days: int) -> date:
            current_date = start_date
            step = -1 if days < 0 else 1
            days_to_add = abs(days)
            while days_to_add > 0:
                current_date += timedelta(days=step)
                if mock_calendar_service.is_working_day(current_date):
                    days_to_add -= 1
            return current_date
        mock_calendar_service.add_business_days.side_effect = custom_add_business_days

        # Required by: Jan 31 (Wed). Lead time: 5 business days
        # Jan 31 (Wed)
        # -1: Jan 30 (Tue)
        # -2: Jan 29 (Mon)
        # -3: Jan 28 (Sun) - skip
        # -3: Jan 27 (Sat) - skip
        # -3: Jan 26 (Fri) - holiday, skip
        # -3: Jan 25 (Thu) - holiday, skip
        # -3: Jan 24 (Wed)
        # -4: Jan 23 (Tue)
        # -5: Jan 22 (Mon)
        # Expected: Jan 22
        components = calculator.LeadTimeComponents(production_days=5)
        result = await calculator.calculate_optimal_required_on_site_date(self.REQUIRED_BY_DATE, components)
        assert result.optimal_required_on_site_date == date(2024, 1, 22)


    # --- Alerting (test_012-016) ---
    async def test_012_r14_date_passed_critical(self, calculator, mock_calendar_service):
        """Tests alert when optimal date has already passed."""
        # Required by Jan 31. Optimal date was Jan 20. Current date (for comparison) is Jan 25.
        # This means optimal date has passed relative to required_by_date logic.
        
        # To simulate optimal date passing, we calculate with lead time
        # then set the REQUIRED_BY_DATE in the alert check to something earlier than optimal date + lead time.
        
        # Let's say lead time is 10 days, required by Jan 31. Optimal is Jan 21.
        # But if the current date is Jan 25 (after optimal Jan 21), it's passed.
        
        # For this test, we are evaluating the margin *between* optimal date and required_by_date
        # required_by_date = Jan 31
        # components = 15 days total lead time -> optimal = Jan 16
        # The alert should be triggered based on `required_by_date` vs `current date`.
        
        # Simpler approach: `required_by_date` is the deadline for the item.
        # The "alert_r14_date_passed" implies `required_by_date` is earlier than `today`.
        
        # For this rule, we need the `current_date` as a parameter to the alert check.
        # The rule is: (optimal_required_on_site_date + total_lead_time) vs REQUIRED_BY_DATE
        # If optimal_required_on_site_date + total_lead_time is LATER than REQUIRED_BY_DATE, it's a problem.

        # Let's assume the alert check method takes `current_date` and `required_by_date` as inputs.
        
        # Scenario: Calculation starts on Jan 25 (current_date). Item needed by Jan 24.
        # Alerts are generated based on the optimal date vs current date and required_by_date.
        # So we need to call `generate_alerts` directly.
        
        # Let's re-evaluate how the alerts are meant to be generated.
        # It's an alert related to the gap between `optimal_required_on_site_date` and `required_by_date`.
        # This implies: calculate optimal date, then compare it to required_by_date.
        # If optimal_date > required_by_date, it means we can't make the deadline.
        
        optimal_date = date(2024, 1, 20) # We need to have item on site by Jan 20
        required_by_date = date(2024, 1, 15) # But client needs it by Jan 15

        alerts = await calculator._check_deadlines(optimal_date, required_by_date)
        assert len(alerts) == 1
        assert alerts[0].status == calculator.LeadTimeStatus.DATE_PASSED
        assert alerts[0].severity == calculator.LeadTimeSeverity.CRITICAL

    async def test_013_alert_r14_tight_margin_3_days(self, calculator, mock_calendar_service):
        """Tests alert when margin is tight (e.g., 3 days)."""
        optimal_date = date(2024, 1, 20)
        required_by_date = date(2024, 1, 23) # Only 3 calendar days margin
        
        alerts = await calculator._check_deadlines(optimal_date, required_by_date)
        assert len(alerts) == 1
        assert alerts[0].status == calculator.LeadTimeStatus.TIGHT_MARGIN
        assert alerts[0].severity == calculator.LeadTimeSeverity.WARNING

    async def test_014_alert_severity_critical_passed(self, calculator):
        optimal_date = date(2024, 1, 20)
        required_by_date = date(2024, 1, 19) # Optimal is later than required_by
        alerts = await calculator._check_deadlines(optimal_date, required_by_date)
        assert alerts[0].severity == calculator.LeadTimeSeverity.CRITICAL

    async def test_015_alert_severity_warning_tight(self, calculator):
        optimal_date = date(2024, 1, 20)
        required_by_date = date(2024, 1, 23) # 3 days margin
        alerts = await calculator._check_deadlines(optimal_date, required_by_date)
        assert alerts[0].severity == calculator.LeadTimeSeverity.WARNING

    async def test_016_no_alert_sufficient_margin(self, calculator):
        optimal_date = date(2024, 1, 20)
        required_by_date = date(2024, 1, 25) # 5 days margin
        alerts = await calculator._check_deadlines(optimal_date, required_by_date)
        assert len(alerts) == 0
