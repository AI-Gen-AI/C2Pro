"""
I12 - Eval Regression Runner Contract (RED)
Test Suite ID: TS-I12-OBS-APP-003
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.modules.observability.application.ports import EvaluationHarness, LangSmithAdapter
from src.modules.observability.domain.entities import EvalMetricResult


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
async def test_i12_run_eval_regression_happy_path_returns_metric_results_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-003:
    run_eval_regression returns EvalMetricResult items for recent dataset metrics.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.87, "groundedness": 0.91},
        "baseline_metrics": {"recall": 0.90, "groundedness": 0.93},
    }

    results = await harness.run_eval_regression(
        dataset_name="extraction_eval_dataset",
        model_version="gpt-4.1-mini-2026-02-18",
    )

    assert results
    assert all(isinstance(item, EvalMetricResult) for item in results)
    mock_langsmith_adapter.get_dataset_eval_metrics.assert_awaited_once_with("extraction_eval_dataset")


@pytest.mark.asyncio
async def test_i12_run_eval_regression_handles_empty_dataset_metrics_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-003:
    empty recent metrics should return an empty list instead of raising.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {"recent_metrics": {}, "baseline_metrics": {}}

    results = await harness.run_eval_regression(
        dataset_name="empty_eval_dataset",
        model_version="gpt-4.1-mini-2026-02-18",
    )

    assert results == []


@pytest.mark.asyncio
async def test_i12_run_eval_regression_propagates_model_version_and_is_deterministic_red(
    harness: EvaluationHarness,
    mock_langsmith_adapter: AsyncMock,
) -> None:
    """
    TS-I12-OBS-APP-003:
    model_version must be propagated and output ordering must be deterministic.
    """
    mock_langsmith_adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"z_metric": 0.2, "a_metric": 0.9, "m_metric": 0.5},
        "baseline_metrics": {},
    }

    results = await harness.run_eval_regression(
        dataset_name="ordered_eval_dataset",
        model_version="model-v123",
    )

    assert [item.metric_name for item in results] == ["a_metric", "m_metric", "z_metric"]
    assert all(item.metadata.get("dataset") == "ordered_eval_dataset" for item in results)
    assert all(item.metadata.get("model_version") == "model-v123" for item in results)
