"""
I7 - Score Aggregation (Domain)
Test Suite ID: TS-I7-SCORE-DOM-001
"""

from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

try:
    from src.modules.coherence.domain.entities import CoherenceAlert
    from src.modules.scoring.domain.entities import OverallScore, ScoreConfig
    from src.modules.scoring.domain.services import ScoreAggregator
except ImportError:
    class CoherenceAlert(BaseModel):
        alert_id: str = Field(default_factory=lambda: str(uuid4()))
        type: str
        severity: str
        message: str
        evidence: dict[str, Any] = Field(default_factory=dict)
        triggered_by_rule: str
        metadata: dict[str, Any] = Field(default_factory=dict)

    class ScoreConfig(BaseModel):
        severity_weights: dict[str, float]
        alert_type_multipliers: dict[str, float]
        severity_thresholds: dict[str, float]

    class OverallScore(BaseModel):
        score: float
        severity: str
        explanation: dict[str, Any] = Field(default_factory=dict)

    class ScoreAggregator:
        def __init__(self, config: ScoreConfig):
            self.config = config

        def aggregate_score(self, alerts: list[CoherenceAlert]) -> OverallScore:
            return OverallScore(score=0.0, severity="Low", explanation={})


@pytest.fixture
def default_score_config() -> ScoreConfig:
    return ScoreConfig(
        severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
        alert_type_multipliers={
            "Schedule Mismatch": 1.5,
            "Budget Mismatch": 1.2,
            "Scope-Procurement Mismatch": 1.0,
        },
        severity_thresholds={"Critical": 2.0, "High": 1.0, "Medium": 0.5},
    )


@pytest.fixture
def mock_alerts_for_aggregation() -> list[CoherenceAlert]:
    return [
        CoherenceAlert(
            type="Schedule Mismatch",
            severity="Critical",
            message="Schedule delayed materially.",
            evidence={},
            triggered_by_rule="R1",
        ),
        CoherenceAlert(
            type="Budget Mismatch",
            severity="High",
            message="Budget exceeded materially.",
            evidence={},
            triggered_by_rule="R2",
        ),
        CoherenceAlert(
            type="Scope-Procurement Mismatch",
            severity="Medium",
            message="Missing scope procurement items.",
            evidence={},
            triggered_by_rule="R3",
        ),
    ]


def test_i7_weighted_aggregation_calculates_correct_overall_score(
    mock_alerts_for_aggregation: list[CoherenceAlert],
    default_score_config: ScoreConfig,
) -> None:
    """Refers to I7.1: weighted score aggregation and severity mapping must be deterministic."""
    aggregator = ScoreAggregator(config=default_score_config)
    overall_score = aggregator.aggregate_score(mock_alerts_for_aggregation)

    assert isinstance(overall_score, OverallScore)
    assert overall_score.score == pytest.approx(2.74)
    assert overall_score.severity == "Critical"


def test_i7_aggregation_is_deterministic_for_same_alert_set(
    mock_alerts_for_aggregation: list[CoherenceAlert],
    default_score_config: ScoreConfig,
) -> None:
    """Refers to I7.3: same input alerts must always produce same score/severity."""
    aggregator = ScoreAggregator(config=default_score_config)

    score_a = aggregator.aggregate_score(mock_alerts_for_aggregation)
    score_b = aggregator.aggregate_score(mock_alerts_for_aggregation)

    assert score_a.score == pytest.approx(score_b.score)
    assert score_a.severity == score_b.severity
