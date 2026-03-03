"""
Refers to Suite IDs: TS-I7-SCORE-DOM-001, TS-I7-SCORE-PROFILES-001.

RED hardening tests for I7 score configuration and aggregation contracts.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.coherence.domain.entities import CoherenceAlert
from src.modules.scoring.domain.entities import ScoreConfig
from src.modules.scoring.domain.services import ScoreAggregator


def test_i7_score_config_rejects_negative_severity_weight_red() -> None:
    """I7 hardening: score config must reject negative severity weights."""
    with pytest.raises(ValidationError):
        ScoreConfig(
            severity_weights={"Critical": -1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
            alert_type_multipliers={"Schedule Mismatch": 1.5},
            severity_thresholds={"Critical": 2.0, "High": 1.0, "Medium": 0.5},
        )


def test_i7_score_config_requires_complete_threshold_keys_red() -> None:
    """I7 hardening: threshold config must require Critical/High/Medium keys."""
    with pytest.raises(ValidationError):
        ScoreConfig(
            severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
            alert_type_multipliers={"Schedule Mismatch": 1.5},
            severity_thresholds={"High": 1.0, "Medium": 0.5},
        )


def test_i7_score_config_rejects_non_monotonic_thresholds_red() -> None:
    """I7 hardening: thresholds must be monotonic Critical >= High >= Medium."""
    with pytest.raises(ValidationError):
        ScoreConfig(
            severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
            alert_type_multipliers={"Schedule Mismatch": 1.5},
            severity_thresholds={"Critical": 0.9, "High": 1.0, "Medium": 0.5},
        )


def test_i7_aggregator_rejects_unknown_severity_red() -> None:
    """I7 hardening: aggregator must fail fast on unknown severity taxonomy."""
    config = ScoreConfig(
        severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
        alert_type_multipliers={"Schedule Mismatch": 1.5},
        severity_thresholds={"Critical": 2.0, "High": 1.0, "Medium": 0.5},
    )
    aggregator = ScoreAggregator(config=config)

    # Build a malformed alert without validation to simulate taxonomy drift in upstream data.
    malformed_alert = CoherenceAlert.model_construct(
        alert_id=uuid4(),
        type="Schedule Mismatch",
        severity="Sev-9",
        message="Malformed severity should be rejected by scoring.",
        evidence={},
        triggered_by_rule="ScheduleRule",
        doc_id=None,
        metadata={},
    )

    with pytest.raises(ValueError, match="severity"):
        aggregator.aggregate_score([malformed_alert])
