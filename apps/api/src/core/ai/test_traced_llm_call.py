"""TS-AI-LANGSMITH-002: Tests for @traced_llm_call decorator behavior."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import asyncio
import time

import pytest

from src.core.ai.langsmith_client import LangSmithClient
from src.core.ai.traced_llm_call import get_current_trace_context, traced_llm_call


class _RecordingSpanClient:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.end_calls: list[dict[str, Any]] = []

    def start_span(
        self,
        name: str,
        input: dict[str, Any] | None = None,
        run_type: str = "llm",
        **kwargs: Any,
    ) -> dict[str, Any]:
        call = {
            "name": name,
            "input": input,
            "run_type": run_type,
            **kwargs,
        }
        self.start_calls.append(call)
        return {"span_id": "span-1"}

    def end_span(self, span: Any, outputs: dict[str, Any] | None = None) -> None:
        self.end_calls.append({"span": span, "outputs": outputs})


class _RecordingUsageLogger:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def log_success(self, record: Any) -> None:
        self.records.append(record)


def test_traced_llm_call_records_successful_async_span(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    span_client = _RecordingSpanClient()
    langsmith_wrapper = LangSmithClient(project_name="c2pro-test")

    @traced_llm_call(
        task_type="coherence",
        span_name="coherence_eval",
        extra_tags=["suite:TS-AI-LANGSMITH-002"],
        client=langsmith_wrapper,
    )
    async def _evaluate(*, tenant_id: str, langsmith_client: _RecordingSpanClient) -> dict[str, str]:
        return {"status": "ok"}

    result = asyncio.run(_evaluate(tenant_id="tenant-123", langsmith_client=span_client))

    assert result == {"status": "ok"}
    assert span_client.start_calls[0]["name"] == "coherence_eval"
    assert span_client.start_calls[0]["run_type"] == "llm"
    assert "task:coherence" in span_client.start_calls[0]["tags"]
    assert "tenant:tenant-123" in span_client.start_calls[0]["tags"]
    assert span_client.start_calls[0]["metadata"]["task_type"] == "coherence"
    assert span_client.end_calls[0]["outputs"]["status"] == "success"


def test_traced_llm_call_records_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    span_client = _RecordingSpanClient()
    langsmith_wrapper = LangSmithClient(project_name="c2pro-test")

    @traced_llm_call(task_type="extraction", client=langsmith_wrapper)
    async def _boom(*, langsmith_client: _RecordingSpanClient) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(_boom(langsmith_client=span_client))

    assert span_client.end_calls[0]["outputs"]["status"] == "error"


def test_traced_llm_call_preserves_sync_function_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

    span_client = _RecordingSpanClient()
    langsmith_wrapper = LangSmithClient(project_name="c2pro-test")

    @traced_llm_call(task_type="routing", client=langsmith_wrapper)
    def _sync_call(*, langsmith_client: _RecordingSpanClient) -> str:
        return "done"

    assert _sync_call.__name__ == "_sync_call"
    assert _sync_call(langsmith_client=span_client) == "done"
    assert span_client.start_calls == []
    assert span_client.end_calls == []


def test_traced_llm_call_captures_prompt_model_usage_and_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    span_client = _RecordingSpanClient()
    langsmith_wrapper = LangSmithClient(project_name="c2pro-test")

    @traced_llm_call(
        task_type="coherence",
        span_name="llm_call_with_metrics",
        extra_tags=["suite:TS-AI-LANGSMITH-002"],
        client=langsmith_wrapper,
    )
    async def _evaluate(
        *,
        tenant_id: str,
        prompt: str,
        model_name: str,
        model_params: dict[str, Any],
        langsmith_client: _RecordingSpanClient,
    ) -> dict[str, Any]:
        time.sleep(0.001)
        return {
            "output": "analysis completed",
            "usage": {"prompt_tokens": 111, "completion_tokens": 24, "total_tokens": 135},
            "model_name": model_name,
            "cost_usd": 0.0042,
        }

    asyncio.run(
        _evaluate(
            tenant_id="tenant-321",
            prompt="Summarize project risks.",
            model_name="gpt-4o-mini",
            model_params={"temperature": 0.2, "max_tokens": 512},
            langsmith_client=span_client,
        ),
    )

    start_call = span_client.start_calls[0]
    end_call = span_client.end_calls[0]["outputs"]

    assert start_call["input"]["prompt"] == "Summarize project risks."
    assert start_call["input"]["model_name"] == "gpt-4o-mini"
    assert start_call["input"]["model_params"] == {"temperature": 0.2, "max_tokens": 512}
    assert end_call["status"] == "success"
    assert end_call["output"] == "analysis completed"
    assert end_call["tokens_input"] == 111
    assert end_call["tokens_output"] == 24
    assert end_call["tokens_total"] == 135
    assert end_call["cost_usd"] == 0.0042
    assert isinstance(end_call["latency_ms"], int)
    assert end_call["latency_ms"] >= 1


def test_traced_llm_call_persists_trace_to_usage_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    span_client = _RecordingSpanClient()
    usage_logger = _RecordingUsageLogger()
    langsmith_wrapper = LangSmithClient(project_name="c2pro-test")
    tenant_id = uuid4()

    @traced_llm_call(task_type="coherence", client=langsmith_wrapper)
    async def _evaluate(
        *,
        tenant_id: Any,
        prompt_version: str,
        langsmith_client: _RecordingSpanClient,
        usage_logger: _RecordingUsageLogger,
    ) -> dict[str, Any]:
        return {
            "output": "analysis completed",
            "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
            "model_name": "claude-sonnet-4",
            "cost_usd": 0.001,
            "operation_type": "coherence",
        }

    asyncio.run(
        _evaluate(
            tenant_id=tenant_id,
            prompt_version="v1",
            langsmith_client=span_client,
            usage_logger=usage_logger,
        ),
    )

    assert usage_logger.records
    record = usage_logger.records[0]
    assert record.tenant_id == tenant_id
    assert record.trace_id == "span-1"
    assert record.operation == "coherence"
    assert get_current_trace_context() is None
