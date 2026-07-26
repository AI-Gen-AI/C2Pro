"""
SLA Calculator Domain Service.

Pure Python service for calculating SLA policies and due dates based on alert severity.
NO framework imports - completely isolated domain logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AlertSeverityLevel(StrEnum):
    """Alert severity levels for SLA calculation."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SLAPolicy:
    """SLA policy definition with name and response time in hours."""
    name: str
    response_hours: int


@dataclass
class SLACalculation:
    """Result of SLA calculation."""
    policy_name: str | None
    due_at: datetime | None
    hours_remaining: int | None
    is_overdue: bool


CRITICAL_SLA = SLAPolicy(
    name="Critical severity: first response in 2 hours",
    response_hours=2,
)
HIGH_SLA = SLAPolicy(
    name="High severity: response in 24 hours",
    response_hours=24,
)
MEDIUM_SLA = SLAPolicy(
    name="Medium severity: response in 72 hours",
    response_hours=72,
)
LOW_SLA = SLAPolicy(
    name="Low severity: response in 120 hours",
    response_hours=120,
)

SEVERITY_TO_SLA: dict[AlertSeverityLevel, SLAPolicy] = {
    AlertSeverityLevel.CRITICAL: CRITICAL_SLA,
    AlertSeverityLevel.HIGH: HIGH_SLA,
    AlertSeverityLevel.MEDIUM: MEDIUM_SLA,
    AlertSeverityLevel.LOW: LOW_SLA,
}


class SLACalculator:
    """
    Domain service for calculating SLA policies and due dates.

    Pure domain logic with no external dependencies.
    """

    @staticmethod
    def get_sla_policy(severity: str | AlertSeverityLevel) -> SLAPolicy | None:
        """
        Get SLA policy for a given severity level.

        Args:
            severity: Alert severity as string or AlertSeverityLevel enum

        Returns:
            SLAPolicy if severity is valid, None otherwise
        """
        if isinstance(severity, str):
            try:
                severity = AlertSeverityLevel(severity.lower())
            except ValueError:
                return None
        return SEVERITY_TO_SLA.get(severity)

    @staticmethod
    def calculate_due_at(
        severity: str | AlertSeverityLevel,
        created_at: datetime,
    ) -> tuple[str | None, datetime]:
        """
        Calculate SLA due date based on severity and creation time.

        Args:
            severity: Alert severity level
            created_at: When the alert was created

        Returns:
            Tuple of (policy_name, due_at) - due_at is datetime.min if no policy found
        """
        policy = SLACalculator.get_sla_policy(severity)
        if policy is None:
            return None, datetime.min

        due_at = created_at + timedelta(hours=policy.response_hours)
        return policy.name, due_at

    @staticmethod
    def calculate(
        severity: str | AlertSeverityLevel,
        created_at: datetime,
    ) -> SLACalculation:
        """
        Calculate full SLA information including overdue status.

        Args:
            severity: Alert severity level
            created_at: When the alert was created

        Returns:
            SLACalculation with policy name, due date, hours remaining, and overdue status
        """
        policy_name, due_at = SLACalculator.calculate_due_at(severity, created_at)

        if policy_name is None:
            return SLACalculation(
                policy_name=None,
                due_at=None,
                hours_remaining=None,
                is_overdue=False,
            )

        now = datetime.now(UTC)
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)

        hours_remaining = (due_at - now).total_seconds() / 3600
        is_overdue = hours_remaining < 0

        return SLACalculation(
            policy_name=policy_name,
            due_at=due_at,
            hours_remaining=int(hours_remaining) if hours_remaining >= 0 else int(hours_remaining),
            is_overdue=is_overdue,
        )

    @staticmethod
    def get_all_policies() -> list[SLAPolicy]:
        """Return all defined SLA policies."""
        return [
            CRITICAL_SLA,
            HIGH_SLA,
            MEDIUM_SLA,
            LOW_SLA,
        ]

    @staticmethod
    def validate_severity(severity: str | AlertSeverityLevel) -> bool:
        """
        Validate that a severity level has an associated SLA policy.

        Args:
            severity: Severity level to validate

        Returns:
            True if valid, False otherwise
        """
        return SLACalculator.get_sla_policy(severity) is not None
