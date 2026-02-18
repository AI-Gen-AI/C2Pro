"""
I12 - Drift Detection Edge Cases (RED)
Test Suite ID: TS-I12-OBS-APP-005
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.modules.observability.application.ports import EvaluationHarness, LangSmithAdapter
from src.modules.observability.domain.entities import DriftAlarmConfig


@pytest.fixture
def mock_langsmith_adapter() -> AsyncMock:
    return AsyncMock(spec=LangSmithAdapter)


@pytest.fixture
def mock_notification_service() -> AsyncMock:
    notification = AsyncMock()
    notification.send_escalation_alert.return_value = None
    return notification


@pytest.fixture
def harness(
    mock_langsmith_adapter: AsyncMock,
    mock_notification_service: AsyncMock,
) -> EvaluationHarness:
    return EvaluationHarness(
        langsmith_adapter=mock_langsmith_adapter,
        notification_service=mock_notification_service,
    )


@pytest.mark.asyncio
async def test_i12_check_drift_baseline_zero_uses_absolute_guard_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
    mock_notification_service: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-005:
    baseline=0 must not crash percentage computation and should still apply absolute guard.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.10},
        "baseline_metrics": {"recall": 0.0},
    }

    alerts = await harness.check_drift(
        dataset_name="edge_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.20,
                min_absolute_value=0.50,
                escalation_target_email="ops@c2pro.ai",
            )
        ],
    )

    assert len(alerts) == 1
    assert alerts[0].metric_name == "recall"
    mock_notification_service.send_escalation_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_i12_check_drift_triggers_on_exact_threshold_boundary_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-005:
    exact threshold boundary must be treated as drift (>= threshold).
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.90},
        "baseline_metrics": {"recall": 1.00},
    }

    alerts = await harness.check_drift(
        dataset_name="edge_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.10,
                min_absolute_value=None,
                escalation_target_email="ops@c2pro.ai",
            )
        ],
    )

    assert len(alerts) == 1
    assert "percentage drop exceeded threshold" in alerts[0].message


@pytest.mark.asyncio
async def test_i12_check_drift_triggers_on_exact_min_absolute_boundary_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-005:
    exact minimum absolute boundary must still trigger drift (<= boundary).
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.80},
        "baseline_metrics": {"recall": 0.82},
    }

    alerts = await harness.check_drift(
        dataset_name="edge_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.50,
                min_absolute_value=0.80,
                escalation_target_email="ops@c2pro.ai",
            )
        ],
    )

    assert len(alerts) == 1
    assert "minimum absolute value" in alerts[0].message


@pytest.mark.asyncio
async def test_i12_check_drift_mixed_multimetric_returns_only_affected_alerts_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-005:
    mixed metric scenarios should produce alerts only for impacted metrics.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.70, "groundedness": 0.95, "faithfulness": 0.50},
        "baseline_metrics": {"recall": 0.90, "groundedness": 0.96, "faithfulness": 0.51},
    }

    alerts = await harness.check_drift(
        dataset_name="edge_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.20,
                min_absolute_value=None,
                escalation_target_email="ops@c2pro.ai",
            ),
            DriftAlarmConfig(
                metric_name="groundedness",
                threshold_percentage_drop=0.20,
                min_absolute_value=None,
                escalation_target_email="ops@c2pro.ai",
            ),
            DriftAlarmConfig(
                metric_name="faithfulness",
                threshold_percentage_drop=0.01,
                min_absolute_value=0.50,
                escalation_target_email="ops@c2pro.ai",
            ),
        ],
    )

    metric_names = [alert.metric_name for alert in alerts]
    assert metric_names == ["recall", "faithfulness"]
