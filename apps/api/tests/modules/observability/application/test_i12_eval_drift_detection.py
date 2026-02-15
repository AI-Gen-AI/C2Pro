"""
I12 - Evaluation Drift Detection (Application)
Test Suite ID: TS-I12-OBS-APP-002
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.observability.application.ports import EvaluationHarness, LangSmithAdapter
from src.modules.observability.domain.entities import DriftAlarmConfig


@pytest.fixture
def mock_langsmith_adapter() -> AsyncMock:
    adapter = AsyncMock(spec=LangSmithAdapter)
    adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.82, "groundedness": 0.90},
        "baseline_metrics": {"recall": 0.90, "groundedness": 0.95},
    }
    return adapter


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
async def test_i12_eval_harness_detects_recall_drift(
    harness: EvaluationHarness,
    mock_notification_service: AsyncMock,
) -> None:
    """Refers to I12.3: drift alarm must trigger when recall drops past threshold."""
    alerts = await harness.check_drift(
        dataset_name="extraction_eval_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.05,
                min_absolute_value=0.80,
                escalation_target_email="ops@c2pro.ai",
            )
        ],
    )

    assert len(alerts) == 1
    assert alerts[0].metric_name == "recall"
    assert alerts[0].is_drift_detected is True
    mock_notification_service.send_escalation_alert.assert_called_once()


@pytest.mark.asyncio
async def test_i12_drift_alarm_configuration_is_required(harness: EvaluationHarness) -> None:
    """Refers to I12.4: drift checks must fail fast when alarm config is missing."""
    with pytest.raises(ValueError, match="Drift alarm configuration is required."):
        await harness.check_drift(dataset_name="extraction_eval_dataset", alarm_configs=[])

