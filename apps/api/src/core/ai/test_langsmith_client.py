"""TS-AI-LANGSMITH-001: Unit tests for LangSmith client wrapper."""

from __future__ import annotations

import os

from src.core.ai.langsmith_client import LangSmithClient


def test_langsmith_client_disabled_without_api_key(monkeypatch):
    """TS-AI-LANGSMITH-001: Client disables tracing when API key is absent."""
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    client = LangSmithClient(project_name="c2pro-test")

    assert client.enabled is False


def test_langsmith_client_builds_metadata_tags(monkeypatch):
    """TS-AI-LANGSMITH-001: Tags and metadata always include tenant/task context."""
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    client = LangSmithClient(project_name="c2pro-test")

    tags = client.build_tags(task_type="coherence", tenant_id="tenant-123", extra_tags=["pipeline"])
    metadata = client.build_metadata(request_id="req-1", tenant_id="tenant-123", task_type="coherence")

    assert "pipeline" in tags
    assert "task:coherence" in tags
    assert "tenant:tenant-123" in tags
    assert metadata["request_id"] == "req-1"
    assert metadata["tenant_id"] == "tenant-123"
    assert metadata["task_type"] == "coherence"
    assert metadata["environment"] == os.getenv("ENVIRONMENT", "development")


def test_langsmith_client_start_span_supplies_default_inputs(monkeypatch):
    """TS-AI-LANGSMITH-001: LangSmith span creation satisfies current SDK contract."""

    class _FakeRun:
        id = "run-1"

    class _FakeNativeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def create_run(self, **kwargs):
            self.calls.append(kwargs)
            return _FakeRun()

    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    client = LangSmithClient(project_name="c2pro-test")
    fake_native_client = _FakeNativeClient()
    client._client = fake_native_client

    client.start_span(name="coherence_node:prepare_context", run_type="chain")

    assert fake_native_client.calls == [
        {
            "name": "coherence_node:prepare_context",
            "run_type": "chain",
            "inputs": {},
            "metadata": {},
            "project_name": "c2pro-test",
            "parent_run": None,
        }
    ]


def test_langsmith_client_start_span_fails_open_on_api_error(monkeypatch):
    """TS-AI-LANGSMITH-001: LangSmith API failures must not block application responses."""

    class _FailingNativeClient:
        def create_run(self, **kwargs):
            raise RuntimeError("403 Forbidden")

    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    client = LangSmithClient(project_name="c2pro-test")
    client._client = _FailingNativeClient()

    assert client.start_span(name="rag_answer", run_type="llm") is None
