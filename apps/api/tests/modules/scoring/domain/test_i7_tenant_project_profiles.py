"""
I7 - Tenant/Project Score Profiles (Domain)
Test Suite ID: TS-I7-SCORE-PROFILES-001
"""

from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

try:
    from src.modules.coherence.domain.entities import CoherenceAlert
    from src.modules.scoring.domain.entities import ScoreConfig
    from src.modules.scoring.domain.services import ScoreAggregator
except ImportError:
    class CoherenceAlert(BaseModel):
        alert_id: str = Field(default_factory=lambda: str(uuid4()))
        type: str
        severity: str
        message: str
        evidence: dict[str, Any] = Field(default_factory=dict)
        triggered_by_rule: str

    class ScoreConfig(BaseModel):
        severity_weights: dict[str, float]
        alert_type_multipliers: dict[str, float]
        severity_thresholds: dict[str, float]

    class _ScoreResult(BaseModel):
        score: float
        severity: str

    class ScoreAggregator:
        def __init__(self, config: ScoreConfig):
            self.config = config

        def aggregate_score(self, alerts: list[CoherenceAlert]) -> _ScoreResult:
            return _ScoreResult(score=0.0, severity="Low")


@pytest.fixture
def tenant_a_score_config() -> ScoreConfig:
    return ScoreConfig(
        severity_weights={"Critical": 2.0, "High": 1.0, "Medium": 0.5, "Low": 0.2},
        alert_type_multipliers={"Schedule Mismatch": 2.0, "Budget Mismatch": 1.5},
        severity_thresholds={"Critical": 3.0, "High": 1.5, "Medium": 0.7},
    )


@pytest.fixture
def tenant_b_score_config() -> ScoreConfig:
    return ScoreConfig(
        severity_weights={"Critical": 0.8, "High": 0.5, "Medium": 0.3, "Low": 0.1},
        alert_type_multipliers={"Schedule Mismatch": 1.0, "Budget Mismatch": 1.0},
        severity_thresholds={"Critical": 1.5, "High": 0.8, "Medium": 0.4},
    )


@pytest.fixture
def project_x_score_config() -> ScoreConfig:
    return ScoreConfig(
        severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
        alert_type_multipliers={"Schedule Mismatch": 5.0, "Budget Mismatch": 0.5},
        severity_thresholds={"Critical": 2.0, "High": 1.0, "Medium": 0.5},
    )


@pytest.fixture
def mock_alerts_for_tenant() -> list[CoherenceAlert]:
    return [
        CoherenceAlert(
            type="Schedule Mismatch",
            severity="High",
            message="Schedule delayed materially.",
            evidence={},
            triggered_by_rule="R1",
        ),
        CoherenceAlert(
            type="Budget Mismatch",
            severity="Medium",
            message="Budget drift detected.",
            evidence={},
            triggered_by_rule="R2",
        ),
    ]


def test_i7_tenant_specific_weights_are_applied(
    mock_alerts_for_tenant: list[CoherenceAlert],
    tenant_a_score_config: ScoreConfig,
    tenant_b_score_config: ScoreConfig,
) -> None:
    """Refers to I7.2: tenant-specific profiles must change score outcome deterministically."""
    score_a = ScoreAggregator(config=tenant_a_score_config).aggregate_score(mock_alerts_for_tenant)
    score_b = ScoreAggregator(config=tenant_b_score_config).aggregate_score(mock_alerts_for_tenant)

    assert score_a.score == pytest.approx(2.75)
    assert score_b.score == pytest.approx(0.8)
    assert score_a.score != score_b.score


def test_i7_project_specific_thresholds_are_applied(
    mock_alerts_for_tenant: list[CoherenceAlert],
    project_x_score_config: ScoreConfig,
) -> None:
    """Refers to I7.2: project profile thresholds/multipliers must be applied without leakage."""
    score_x = ScoreAggregator(config=project_x_score_config).aggregate_score(mock_alerts_for_tenant)

    assert score_x.score == pytest.approx(3.7)
    assert score_x.severity == "Critical"
