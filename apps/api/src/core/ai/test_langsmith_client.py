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
