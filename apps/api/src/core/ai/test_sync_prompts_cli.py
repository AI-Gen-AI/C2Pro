"""TS-AI-LANGSMITH-004: CLI tests for prompt hub sync entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.ai.sync_prompts import run_sync

from src.core.ai.prompt_registry import InMemoryPromptHubClient


def test_run_sync_pushes_discovered_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    template = tmp_path / "coherence_llm_v1.0.jinja2"
    template.write_text("{{ contract_text }}", encoding="utf-8")

    hub = InMemoryPromptHubClient()
    summary = run_sync(templates_root=tmp_path, hub_client=hub)

    assert summary["discovered"] == 1
    assert summary["synced"] == 1
    assert summary["template_names"] == ["coherence_llm"]

    fetched = hub.pull_prompt(template_name="coherence_llm", version="1.0")
    assert fetched is not None
    assert fetched["jinja_content"] == "{{ contract_text }}"


def test_run_sync_with_no_templates_returns_empty_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    summary = run_sync(templates_root=tmp_path, hub_client=InMemoryPromptHubClient())

    assert summary["discovered"] == 0
    assert summary["synced"] == 0
    assert summary["template_names"] == []


def test_run_sync_requires_langsmith_enablement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

    template = tmp_path / "coherence_llm_v1.0.jinja2"
    template.write_text("{{ contract_text }}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Prompt Hub sync unavailable"):
        run_sync(templates_root=tmp_path, hub_client=InMemoryPromptHubClient())
