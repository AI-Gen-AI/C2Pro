"""
I12 - Drift Alert Domain Rules (RED)
Test Suite ID: TS-I12-OBS-DOM-003
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.modules.observability.domain.entities import DriftAlert


def test_i12_drift_alert_requires_complete_metadata_red() -> None:
    """
    TS-I12-OBS-DOM-003:
    domain alerts must carry complete metadata for operations routing.
    """
    with pytest.raises(ValidationError, match="dataset"):
        DriftAlert(
            metric_name="recall",
            baseline_value=0.92,
            recent_value=0.81,
            is_drift_detected=True,
            message="Drift detected for metric recall",
            metadata={"requires_ops_review": True},
        )

    with pytest.raises(ValidationError, match="requires_ops_review"):
        DriftAlert(
            metric_name="recall",
            baseline_value=0.92,
            recent_value=0.81,
            is_drift_detected=True,
            message="Drift detected for metric recall",
            metadata={"dataset": "extraction_eval_dataset"},
        )


def test_i12_drift_alert_requires_message_to_reference_metric_red() -> None:
    """
    TS-I12-OBS-DOM-003:
    alert message must reference the affected metric for deterministic triage.
    """
    with pytest.raises(ValidationError, match="message"):
        DriftAlert(
            metric_name="recall",
            baseline_value=0.92,
            recent_value=0.81,
            is_drift_detected=True,
            message="drift detected",
            metadata={"dataset": "extraction_eval_dataset", "requires_ops_review": True},
        )


def test_i12_drift_alert_metric_values_must_be_unit_interval_red() -> None:
    """
    TS-I12-OBS-DOM-003:
    baseline/recent metric values must stay in [0, 1] as evaluation scores.
    """
    with pytest.raises(ValidationError, match="baseline_value"):
        DriftAlert(
            metric_name="recall",
            baseline_value=1.2,
            recent_value=0.81,
            is_drift_detected=True,
            message="Drift detected for metric recall",
            metadata={"dataset": "extraction_eval_dataset", "requires_ops_review": True},
        )

    with pytest.raises(ValidationError, match="recent_value"):
        DriftAlert(
            metric_name="recall",
            baseline_value=0.92,
            recent_value=-0.1,
            is_drift_detected=True,
            message="Drift detected for metric recall",
            metadata={"dataset": "extraction_eval_dataset", "requires_ops_review": True},
        )
