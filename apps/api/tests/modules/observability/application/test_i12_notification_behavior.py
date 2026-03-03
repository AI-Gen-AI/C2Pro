"""
I12 - Notification Behavior (RED)
Test Suite ID: TS-I12-OBS-APP-006
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
async def test_i12_notification_sends_one_escalation_per_detected_alert_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
    mock_notification_service: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-006:
    each detected alert should trigger exactly one escalation notification.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.70, "groundedness": 0.70},
        "baseline_metrics": {"recall": 0.90, "groundedness": 0.90},
    }

    alerts = await harness.check_drift(
        dataset_name="notify_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.10,
                min_absolute_value=None,
                escalation_target_email="ops@c2pro.ai",
            ),
            DriftAlarmConfig(
                metric_name="groundedness",
                threshold_percentage_drop=0.10,
                min_absolute_value=None,
                escalation_target_email="ops@c2pro.ai",
            ),
        ],
    )

    assert len(alerts) == 2
    assert mock_notification_service.send_escalation_alert.await_count == 2


@pytest.mark.asyncio
async def test_i12_notification_does_not_send_when_no_drift_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
    mock_notification_service: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-006:
    no notification should be sent when no metric crosses configured alarms.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.90},
        "baseline_metrics": {"recall": 0.90},
    }

    alerts = await harness.check_drift(
        dataset_name="notify_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.20,
                min_absolute_value=0.50,
                escalation_target_email="ops@c2pro.ai",
            )
        ],
    )

    assert alerts == []
    mock_notification_service.send_escalation_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_i12_notification_is_idempotent_for_repeated_snapshot_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
    mock_notification_service: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-006:
    repeating the exact same snapshot should not re-escalate the same alert.
    """
    snapshot = {
        "recent_metrics": {"recall": 0.70},
        "baseline_metrics": {"recall": 0.90},
    }
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = snapshot

    alarm_config = DriftAlarmConfig(
        metric_name="recall",
        threshold_percentage_drop=0.10,
        min_absolute_value=None,
        escalation_target_email="ops@c2pro.ai",
    )

    first_alerts = await harness.check_drift(dataset_name="notify_dataset", alarm_configs=[alarm_config])
    second_alerts = await harness.check_drift(dataset_name="notify_dataset", alarm_configs=[alarm_config])

    assert len(first_alerts) == 1
    assert len(second_alerts) == 1
    assert mock_notification_service.send_escalation_alert.await_count == 1
