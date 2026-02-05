"""
Lead time alert evaluation rules.

Refers to Suite ID: TS-UD-PROC-LTM-004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class LeadTimeAlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class LeadTimeAlertCode(str, Enum):
    """Alert codes for procurement lead-time risk."""

    R14_DATE_PASSED = "R14_DATE_PASSED"
    R14_TIGHT_MARGIN = "R14_TIGHT_MARGIN"
    R14_WATCH_WINDOW = "R14_WATCH_WINDOW"


@dataclass(frozen=True)
class LeadTimeAlert:
    """Alert payload for lead-time monitoring."""

    code: LeadTimeAlertCode
    severity: LeadTimeAlertSeverity
    message: str
    metadata: dict[str, int] = field(default_factory=dict)


class LeadTimeAlertEvaluator:
    """Domain service that evaluates lead-time alert conditions."""

    def __init__(self, tight_margin_days: int = 3, watch_window_days: int = 7) -> None:
        self._tight_margin_days = tight_margin_days
        self._watch_window_days = watch_window_days

    def evaluate(self, optimal_order_date: date, current_date: date) -> list[LeadTimeAlert]:
        margin_days = (optimal_order_date - current_date).days
        if margin_days < 0:
            return [
                LeadTimeAlert(
                    code=LeadTimeAlertCode.R14_DATE_PASSED,
                    severity=LeadTimeAlertSeverity.CRITICAL,
                    message="Optimal order date has already passed.",
                    metadata={"overdue_days": abs(margin_days)},
                )
            ]

        if margin_days <= self._tight_margin_days:
            return [
                LeadTimeAlert(
                    code=LeadTimeAlertCode.R14_TIGHT_MARGIN,
                    severity=LeadTimeAlertSeverity.WARNING,
                    message="Tight lead-time margin detected.",
                    metadata={"margin_days": margin_days},
                )
            ]

        if margin_days <= self._watch_window_days:
            return [
                LeadTimeAlert(
                    code=LeadTimeAlertCode.R14_WATCH_WINDOW,
                    severity=LeadTimeAlertSeverity.INFO,
                    message="Lead-time is inside watch window.",
                    metadata={"margin_days": margin_days},
                )
            ]

        return []
