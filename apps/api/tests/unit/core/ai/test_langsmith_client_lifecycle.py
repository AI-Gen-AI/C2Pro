"""TS-AI-LANGSMITH-001: SDK-faithful LangSmith run lifecycle tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.core.ai.langsmith_client import LangSmithClient


class _RecordingNativeClient:
    """TS-AI-LANGSMITH-001: Record native SDK calls without network access."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []

    def create_run(self, **kwargs: Any) -> None:
        """Match langsmith.Client.create_run, which returns None."""
        self.created.append(kwargs)

    def update_run(self, run_id: UUID, **kwargs: Any) -> None:
        """Match langsmith.Client.update_run and record completion payloads."""
        self.updated.append({"run_id": run_id, **kwargs})


def _enabled_wrapper(monkeypatch: Any) -> tuple[LangSmithClient, _RecordingNativeClient]:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    wrapper = LangSmithClient(project_name="c2pro-test", enabled=True)
    native_client = _RecordingNativeClient()
    wrapper._client = native_client
    return wrapper, native_client


def test_start_span_owns_stable_run_id_when_native_create_returns_none(monkeypatch: Any) -> None:
    """TS-AI-LANGSMITH-001: The wrapper owns the ID passed to the native SDK."""
    wrapper, native_client = _enabled_wrapper(monkeypatch)

    span = wrapper.start_span(
        name="coherence_node:prepare_context",
        run_type="chain",
        inputs={"project_id": "project-1"},
    )

    assert span is not None
    assert isinstance(span.id, UUID)
    assert native_client.created[0]["id"] == span.id


def test_end_span_updates_native_run_with_utc_completion_payload(monkeypatch: Any) -> None:
    """TS-AI-LANGSMITH-001: Completion uses update_run with the wrapper-owned ID."""
    wrapper, native_client = _enabled_wrapper(monkeypatch)
    span = wrapper.start_span(name="rag_answer", run_type="llm")
    assert span is not None

    wrapper.end_span(
        span,
        error=RuntimeError("provider timeout"),
        outputs={"status": "error"},
    )

    assert len(native_client.updated) == 1
    completion = native_client.updated[0]
    assert completion["run_id"] == span.id
    assert completion["error"] == "provider timeout"
    assert completion["outputs"] == {"status": "error"}
    assert isinstance(completion["end_time"], datetime)
    assert completion["end_time"].tzinfo is UTC
