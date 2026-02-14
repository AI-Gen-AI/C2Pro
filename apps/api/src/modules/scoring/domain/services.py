"""
I7 Scoring Domain Services
Test Suite IDs: TS-I7-SCORE-DOM-001, TS-I7-SCORE-PROFILES-001
"""

from src.modules.coherence.domain.entities import CoherenceAlert
from src.modules.scoring.domain.entities import OverallScore, ScoreConfig


class ScoreAggregator:
    """Pure deterministic weighted score aggregator."""

    def __init__(self, config: ScoreConfig):
        self.config = config

    def aggregate_score(self, alerts: list[CoherenceAlert]) -> OverallScore:
        score_components: list[dict[str, float | str]] = []
        total_score = 0.0

        for alert in alerts:
            severity_weight = self.config.severity_weights.get(alert.severity, 0.0)
            type_multiplier = self.config.alert_type_multipliers.get(alert.type, 1.0)
            contribution = severity_weight * type_multiplier
            total_score += contribution
            score_components.append(
                {
                    "alert_type": alert.type,
                    "severity": alert.severity,
                    "severity_weight": severity_weight,
                    "type_multiplier": type_multiplier,
                    "contribution": contribution,
                }
            )

        normalized_score = round(total_score, 6)
        severity = self._map_severity(normalized_score)
        return OverallScore(
            score=normalized_score,
            severity=severity,
            explanation={"components": score_components, "thresholds": self.config.severity_thresholds},
        )

    def _map_severity(self, score: float) -> str:
        thresholds = self.config.severity_thresholds
        if score >= thresholds.get("Critical", float("inf")):
            return "Critical"
        if score >= thresholds.get("High", float("inf")):
            return "High"
        if score >= thresholds.get("Medium", float("inf")):
            return "Medium"
        return "Low"

