"""TS-AI-LANGSMITH-VALIDATION-UNIT: Unit coverage for EPIC-LANGSMITH-VALIDATION."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.ai.analytics_service import AIAnalyticsService
from src.core.ai.feedback_router import LangSmithFeedbackClient
from src.core.ai.langsmith_client import LangSmithClient
from src.core.ai.traced_llm_call import traced_llm_call


@pytest.mark.asyncio
async def test_traced_decorator_emits_expected_tags_and_usage_payload() -> None:
    tenant_id = uuid4()
    span_client = MagicMock()
    span_client.start_span.return_value = {"id": "trace-123", "url": "https://smith/runs/trace-123"}

    usage_logger = SimpleNamespace(log_success=AsyncMock())
    langsmith_wrapper = LangSmithClient(enabled=True, project="qa", environment="test")

    @traced_llm_call(task_type="analytics", client=langsmith_wrapper, extra_tags=["suite:validation"])
    async def _call(**_: object) -> dict[str, object]:
        return {
            "output": "done",
            "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            "cost_usd": 0.0021,
            "model_name": "claude-3-5-sonnet",
            "operation_type": "analytics",
        }

    await _call(
        tenant_id=tenant_id,
        prompt="hello",
        prompt_version="v2",
        model_params={"temperature": 0.1},
        langsmith_client=span_client,
        usage_logger=usage_logger,
        request_id="req-1",
    )

    assert span_client.start_span.call_count == 1
    _, kwargs = span_client.start_span.call_args
    assert "task:analytics" in kwargs["tags"]
    assert "tenant" in kwargs["tags"]
    assert "suite:validation" in kwargs["tags"]
    assert kwargs["metadata"]["request_id"] == "req-1"

    usage_logger.log_success.assert_awaited_once()
    saved_record = usage_logger.log_success.await_args.args[0]
    assert saved_record.trace_id == "trace-123"
    assert saved_record.trace_url.endswith("trace-123")
    assert saved_record.input_tokens == 12
    assert saved_record.output_tokens == 6
    assert saved_record.cost_usd == pytest.approx(0.0021)


def test_feedback_client_uses_langsmith_sdk_payload_shape() -> None:
    client = LangSmithFeedbackClient()
    client.create_feedback(run_id="run-22", score=0.8, comment="good")

    sdk_client = client._client
    sdk_client.create_feedback.assert_called_once_with(
        run_id="run-22",
        key="user_score",
        score=0.8,
        comment="good",
    )


@pytest.mark.asyncio
async def test_analytics_aggregation_maps_sql_rows_to_contract() -> None:
    db = AsyncMock()
    bucket = datetime.now(UTC)

    series_result = MagicMock()
    series_result.mappings.return_value.all.return_value = [
        {
            "bucket": bucket,
            "model_name": "claude-3-5-sonnet",
            "prompt_version": "v3",
            "request_count": 3,
            "total_tokens": 300,
            "total_cost": 0.12,
            "avg_latency_ms": 456.0,
        }
    ]
    summary_result = MagicMock()
    summary_result.mappings.return_value.one.return_value = {
        "total_cost": 0.12,
        "total_tokens": 300,
        "total_requests": 3,
    }
    db.execute = AsyncMock(side_effect=[series_result, summary_result])

    service = AIAnalyticsService(db=db, cache=None)
    payload = await service.cost_breakdown(tenant_id=uuid4(), timeframe="7d")

    assert payload["timeframe"] == "7d"
    assert payload["summary"]["total_requests"] == 3
    assert payload["series"][0]["prompt_version"] == "v3"
    assert payload["series"][0]["avg_latency_ms"] == pytest.approx(456.0)
