"""
Lead time alert rules tests.
"""

from datetime import date

from src.procurement.domain.lead_time_alerts import (
    LeadTimeAlertCode,
    LeadTimeAlertEvaluator,
    LeadTimeAlertSeverity,
)


class TestLeadTimeAlerts:
    """Refers to Suite ID: TS-UD-PROC-LTM-004"""

    def test_001_alert_date_passed_critical(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 5),
            current_date=date(2026, 2, 6),
        )

        assert alerts[0].code == LeadTimeAlertCode.R14_DATE_PASSED
        assert alerts[0].severity == LeadTimeAlertSeverity.CRITICAL

    def test_002_alert_date_passed_includes_overdue_days(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 1),
            current_date=date(2026, 2, 6),
        )

        assert alerts[0].metadata["overdue_days"] == 5

    def test_003_alert_tight_margin_3_days_warning(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 8),
            current_date=date(2026, 2, 5),
        )

        assert alerts[0].code == LeadTimeAlertCode.R14_TIGHT_MARGIN
        assert alerts[0].severity == LeadTimeAlertSeverity.WARNING

    def test_004_alert_tight_margin_same_day_warning(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 5),
            current_date=date(2026, 2, 5),
        )

        assert alerts[0].code == LeadTimeAlertCode.R14_TIGHT_MARGIN
        assert alerts[0].metadata["margin_days"] == 0

    def test_005_alert_watch_window_7_days_info(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 12),
            current_date=date(2026, 2, 5),
        )

        assert alerts[0].code == LeadTimeAlertCode.R14_WATCH_WINDOW
        assert alerts[0].severity == LeadTimeAlertSeverity.INFO

    def test_006_alert_watch_window_4_days_info(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 9),
            current_date=date(2026, 2, 5),
        )

        assert alerts[0].code == LeadTimeAlertCode.R14_WATCH_WINDOW
        assert alerts[0].metadata["margin_days"] == 4

    def test_007_no_alert_when_margin_over_watch_window(self) -> None:
        evaluator = LeadTimeAlertEvaluator()
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 14),
            current_date=date(2026, 2, 5),
        )

        assert alerts == []

    def test_008_custom_thresholds_applied(self) -> None:
        evaluator = LeadTimeAlertEvaluator(tight_margin_days=2, watch_window_days=5)
        alerts = evaluator.evaluate(
            optimal_order_date=date(2026, 2, 10),
            current_date=date(2026, 2, 5),
        )

        assert alerts[0].code == LeadTimeAlertCode.R14_WATCH_WINDOW
