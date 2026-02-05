"""
Subscore calculator domain service.

Refers to Suite ID: TS-UD-COH-SCR-001.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CoherenceSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ScoreScope(str, Enum):
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    QUALITY = "QUALITY"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    TIME = "TIME"


class CoherenceAlert(BaseModel):
    rule_id: str
    severity: CoherenceSeverity
    scope: ScoreScope


class SubscoreCalculator:
    """Calculates a category subscore from deterministic alert penalties."""

    BASE_SCORE = 100.0
    MIN_SCORE = 0.0

    _SEVERITY_PENALTIES: dict[CoherenceSeverity, float] = {
        CoherenceSeverity.LOW: 5.0,
        CoherenceSeverity.MEDIUM: 10.0,
        CoherenceSeverity.HIGH: 20.0,
        CoherenceSeverity.CRITICAL: 30.0,
    }

    def calculate_subscore(self, alerts: list[CoherenceAlert], scope: ScoreScope) -> float:
        relevant_alerts = [alert for alert in alerts if alert.scope == scope]
        total_penalty = sum(self._SEVERITY_PENALTIES.get(alert.severity, 0.0) for alert in relevant_alerts)
        return max(self.MIN_SCORE, self.BASE_SCORE - total_penalty)

    async def calculate(self, alerts: list[CoherenceAlert], scope: ScoreScope) -> float:
        # Backward-compatible async wrapper.
        return self.calculate_subscore(alerts=alerts, scope=scope)
