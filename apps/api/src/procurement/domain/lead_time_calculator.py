"""
Lead Time Calculator domain service.

Refers to Suite ID: TS-UD-PROC-LTM-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class LeadTimeSeverity(str, Enum):
    """Alert severity levels for lead time risk."""

    CRITICAL = "critical"
    WARNING = "warning"


class LeadTimeStatus(str, Enum):
    """Lead time alert statuses."""

    DATE_PASSED = "date_passed"
    TIGHT_MARGIN = "tight_margin"


@dataclass(frozen=True)
class LeadTimeAlert:
    """Alert produced by lead time analysis."""

    status: LeadTimeStatus
    severity: LeadTimeSeverity
    message: str


@dataclass(frozen=True)
class LeadTimeBreakdown:
    """Breakdown of lead time components in days."""

    production_days: int
    transit_days: int
    customs_days: int
    buffer_days: int
    total_days: int


@dataclass(frozen=True)
class LeadTimeResult:
    """Lead time calculation result."""

    required_on_site_date: date
    optimal_order_date: date
    lead_time_breakdown: LeadTimeBreakdown
    alerts: list[LeadTimeAlert]


class LeadTimeCalculator:
    """Domain service for procurement lead time calculations."""

    _TIGHT_MARGIN_DAYS: int = 3

    def calculate_optimal_order_date(
        self,
        required_on_site_date: date | None = None,
        start_date: date | None = None,
        production_days: int = 0,
        transit_days: int = 0,
        customs_days: int = 0,
        buffer_days: int = 0,
        use_business_days: bool = False,
        holidays: set[date] | None = None,
        adjust_to_business_day: bool = False,
    ) -> date:
        """Return the optimal order date to hit the required on-site date."""
        target_date = required_on_site_date or start_date
        if target_date is None:
            raise ValueError("required_on_site_date is required")

        total_days = production_days + transit_days + customs_days + buffer_days
        holiday_set = holidays or set()

        if use_business_days:
            optimal = self._subtract_business_days(
                end_date=target_date,
                days=total_days,
                holidays=holiday_set,
            )
            return optimal

        optimal = target_date - timedelta(days=total_days)
        if adjust_to_business_day:
            optimal = self._roll_back_to_business_day(optimal, holiday_set)
        return optimal

    def calculate(
        self,
        required_on_site_date: date,
        production_days: int = 0,
        transit_days: int = 0,
        customs_days: int = 0,
        buffer_days: int = 0,
        use_business_days: bool = False,
        holidays: set[date] | None = None,
        adjust_to_business_day: bool = False,
        current_date: date | None = None,
    ) -> LeadTimeResult:
        """Return lead time result with breakdown and alerts."""
        total_days = production_days + transit_days + customs_days + buffer_days
        optimal_order_date = self.calculate_optimal_order_date(
            required_on_site_date=required_on_site_date,
            production_days=production_days,
            transit_days=transit_days,
            customs_days=customs_days,
            buffer_days=buffer_days,
            use_business_days=use_business_days,
            holidays=holidays,
            adjust_to_business_day=adjust_to_business_day,
        )

        alerts = self._build_alerts(
            optimal_order_date=optimal_order_date,
            current_date=current_date or date.today(),
        )

        breakdown = LeadTimeBreakdown(
            production_days=production_days,
            transit_days=transit_days,
            customs_days=customs_days,
            buffer_days=buffer_days,
            total_days=total_days,
        )
        return LeadTimeResult(
            required_on_site_date=required_on_site_date,
            optimal_order_date=optimal_order_date,
            lead_time_breakdown=breakdown,
            alerts=alerts,
        )

    def _build_alerts(
        self,
        optimal_order_date: date,
        current_date: date,
    ) -> list[LeadTimeAlert]:
        margin_days = (optimal_order_date - current_date).days
        if margin_days < 0:
            return [
                LeadTimeAlert(
                    status=LeadTimeStatus.DATE_PASSED,
                    severity=LeadTimeSeverity.CRITICAL,
                    message="Optimal order date has already passed.",
                )
            ]
        if margin_days <= self._TIGHT_MARGIN_DAYS:
            return [
                LeadTimeAlert(
                    status=LeadTimeStatus.TIGHT_MARGIN,
                    severity=LeadTimeSeverity.WARNING,
                    message="Tight lead time margin.",
                )
            ]
        return []

    def _subtract_business_days(
        self,
        end_date: date,
        days: int,
        holidays: set[date],
    ) -> date:
        current = end_date
        remaining = max(days, 0)
        while remaining > 0:
            current -= timedelta(days=1)
            if self._is_business_day(current, holidays):
                remaining -= 1
        return self._roll_back_to_business_day(current, holidays)

    def _roll_back_to_business_day(self, candidate: date, holidays: set[date]) -> date:
        current = candidate
        while not self._is_business_day(current, holidays):
            current -= timedelta(days=1)
        return current

    @staticmethod
    def _is_business_day(candidate: date, holidays: set[date]) -> bool:
        return candidate.weekday() < 5 and candidate not in holidays
