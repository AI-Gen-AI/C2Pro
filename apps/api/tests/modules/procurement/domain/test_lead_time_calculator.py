"""
Lead Time Calculator basic domain tests.

Refers to Suite ID: TS-UD-PROC-LTM-001.
"""

from datetime import date

from src.procurement.domain.lead_time_calculator import (
    LeadTimeCalculator,
    LeadTimeSeverity,
    LeadTimeStatus,
)


class TestLeadTimeCalculatorBasic:
    """Refers to Suite ID: TS-UD-PROC-LTM-001"""

    def test_001_optimal_date_production_only(self) -> None:
        calculator = LeadTimeCalculator()
        required_on_site = date(2026, 1, 20)

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=required_on_site,
            production_days=10,
        )

        assert result == date(2026, 1, 10)

    def test_002_optimal_date_production_transit(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 20),
            production_days=10,
            transit_days=5,
        )

        assert result == date(2026, 1, 5)

    def test_003_optimal_date_production_transit_buffer(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 20),
            production_days=10,
            transit_days=5,
            buffer_days=2,
        )

        assert result == date(2026, 1, 3)

    def test_004_optimal_date_all_components(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 20),
            production_days=10,
            transit_days=5,
            customs_days=3,
            buffer_days=2,
        )

        assert result == date(2025, 12, 31)

    def test_005_lead_time_breakdown_returned(self) -> None:
        calculator = LeadTimeCalculator()

        detailed = calculator.calculate(
            required_on_site_date=date(2026, 1, 20),
            production_days=10,
            transit_days=5,
            customs_days=3,
            buffer_days=2,
        )

        assert detailed.lead_time_breakdown.production_days == 10
        assert detailed.lead_time_breakdown.transit_days == 5
        assert detailed.lead_time_breakdown.customs_days == 3
        assert detailed.lead_time_breakdown.buffer_days == 2
        assert detailed.lead_time_breakdown.total_days == 20

    def test_006_required_on_site_calculation(self) -> None:
        calculator = LeadTimeCalculator()
        required_on_site = date(2026, 1, 20)

        detailed = calculator.calculate(
            required_on_site_date=required_on_site,
            production_days=1,
        )

        assert detailed.required_on_site_date == required_on_site

    def test_007_business_days_calculation(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 12),  # Monday
            production_days=5,
            use_business_days=True,
        )

        assert result == date(2026, 1, 5)  # Previous Monday

    def test_008_weekend_exclusion(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 12),  # Monday
            production_days=1,
            use_business_days=True,
        )

        assert result == date(2026, 1, 9)  # Friday

    def test_009_holiday_exclusion(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 12),  # Monday
            production_days=1,
            use_business_days=True,
            holidays={date(2026, 1, 9)},  # Friday holiday
        )

        assert result == date(2026, 1, 8)  # Thursday

    def test_010_delivery_on_weekend_adjusted(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 12),  # Monday
            production_days=2,
            adjust_to_business_day=True,
        )

        assert result == date(2026, 1, 9)  # Saturday adjusted to Friday

    def test_011_mixed_calendar_business_days(self) -> None:
        calculator = LeadTimeCalculator()

        result = calculator.calculate_optimal_order_date(
            required_on_site_date=date(2026, 1, 14),  # Wednesday
            production_days=5,
            use_business_days=True,
            holidays={date(2026, 1, 8), date(2026, 1, 9)},
        )

        assert result == date(2026, 1, 5)

    def test_012_alert_r14_date_passed(self) -> None:
        calculator = LeadTimeCalculator()

        detailed = calculator.calculate(
            required_on_site_date=date(2026, 1, 20),
            production_days=5,
            current_date=date(2026, 1, 16),
        )

        assert detailed.alerts[0].status == LeadTimeStatus.DATE_PASSED

    def test_013_alert_r14_tight_margin_3_days(self) -> None:
        calculator = LeadTimeCalculator()

        detailed = calculator.calculate(
            required_on_site_date=date(2026, 1, 20),
            production_days=5,
            current_date=date(2026, 1, 12),
        )

        assert detailed.alerts[0].status == LeadTimeStatus.TIGHT_MARGIN

    def test_014_alert_severity_critical_passed(self) -> None:
        calculator = LeadTimeCalculator()

        detailed = calculator.calculate(
            required_on_site_date=date(2026, 1, 20),
            production_days=5,
            current_date=date(2026, 1, 16),
        )

        assert detailed.alerts[0].severity == LeadTimeSeverity.CRITICAL

    def test_015_alert_severity_warning_tight(self) -> None:
        calculator = LeadTimeCalculator()

        detailed = calculator.calculate(
            required_on_site_date=date(2026, 1, 20),
            production_days=5,
            current_date=date(2026, 1, 12),
        )

        assert detailed.alerts[0].severity == LeadTimeSeverity.WARNING

    def test_016_no_alert_sufficient_margin(self) -> None:
        calculator = LeadTimeCalculator()

        detailed = calculator.calculate(
            required_on_site_date=date(2026, 1, 20),
            production_days=5,
            current_date=date(2026, 1, 10),
        )

        assert detailed.alerts == []
