from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from src.modules.analysis.models import Alert, AlertSeverity, AlertStatus
from src.services.scoring.weights import DEFAULT_SENSITIVITY, SEVERITY_WEIGHTS


@dataclass
class ScoreResult:
    value: int
    severity_breakdown: dict[str, int]
    top_drivers: list[str]
    calculated_at: datetime


class ScoreCalculator:
    """
    Calculates the coherence score using a non-linear decay function:

        score = 100 / (1 + (raw_penalty / sensitivity))

    This keeps scores bounded between 0 and 100 and avoids negative values
    when projects have many alerts.
    """

    def __init__(self, sensitivity: int = DEFAULT_SENSITIVITY) -> None:
        self._sensitivity = sensitivity

    def calculate(self, alerts: Iterable[Alert]) -> ScoreResult:
        open_alerts = [alert for alert in alerts if alert.status == AlertStatus.OPEN]
        raw_penalty = self._raw_penalty(open_alerts)
        normalized = 100 / (1 + (raw_penalty / self._sensitivity))
        score = int(max(0, min(100, normalized)))
        return ScoreResult(
            value=score,
            severity_breakdown=self._severity_breakdown(open_alerts),
            top_drivers=self._top_drivers(open_alerts),
            calculated_at=datetime.utcnow(),
        )

    def _raw_penalty(self, alerts: list[Alert]) -> int:
        total = 0
        for alert in alerts:
            total += SEVERITY_WEIGHTS.get(alert.severity, 0)
        return total

    def _severity_breakdown(self, alerts: list[Alert]) -> dict[str, int]:
        breakdown = {severity.value: 0 for severity in AlertSeverity}
        for alert in alerts:
            breakdown[alert.severity.value] += 1
        return breakdown

    def _top_drivers(self, alerts: list[Alert]) -> list[str]:
        penalties: dict[str, int] = {}
        for alert in alerts:
            if not alert.rule_id:
                continue
            penalties.setdefault(alert.rule_id, 0)
            penalties[alert.rule_id] += SEVERITY_WEIGHTS.get(alert.severity, 0)
        sorted_rules = sorted(penalties.items(), key=lambda item: item[1], reverse=True)
        return [rule_id for rule_id, _ in sorted_rules[:5]]
