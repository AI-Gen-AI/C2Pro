"""TS-AI-LANGSMITH-003: Unit tests for Prompt Registry sync APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.ai.langsmith_client import LangSmithClient
from src.core.ai.prompt_registry import InMemoryPromptHubClient, PromptRegistry


@pytest.fixture
def enabled_registry(monkeypatch: pytest.MonkeyPatch) -> PromptRegistry:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    return PromptRegistry(
        langsmith_client=LangSmithClient(project_name="c2pro-test"),
        hub_client=InMemoryPromptHubClient(),
    )


def test_prompt_registry_sync_pull_and_versions(enabled_registry: PromptRegistry) -> None:
    metadata = enabled_registry.build_template_metadata(
        owner="backend-team",
        description="coherence evaluator",
        tags=["coherence", "production"],
    )

    sync_result = enabled_registry.sync_template_to_hub(
        template_name="coherence_llm",
        version="1.0",
        jinja_content="{{ contract_text }}",
        metadata=metadata,
    )

    fetched = enabled_registry.pull_template_from_hub(template_name="coherence_llm", version="1.0")
    versions = enabled_registry.list_template_versions(template_name="coherence_llm")

    assert sync_result["template_name"] == "coherence_llm"
    assert fetched is not None
    assert fetched["metadata"]["owner"] == "backend-team"
    assert versions == ["1.0"]


def test_prompt_registry_requires_langsmith_enablement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

    registry = PromptRegistry(
        langsmith_client=LangSmithClient(project_name="c2pro-test"),
        hub_client=InMemoryPromptHubClient(),
    )

    with pytest.raises(RuntimeError, match="Prompt Hub sync unavailable"):
        registry.sync_template_to_hub(
            template_name="coherence_llm",
            version="1.0",
            jinja_content="{{ contract_text }}",
        )


def test_prompt_registry_discovers_jinja_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "unit-test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    template_path = tmp_path / "coherence_llm_v1.2.jinja2"
    template_path.write_text("Hello {{ name }}", encoding="utf-8")

    registry = PromptRegistry(
        langsmith_client=LangSmithClient(project_name="c2pro-test"),
        hub_client=InMemoryPromptHubClient(),
        templates_root=tmp_path,
    )

    records = registry.discover_templates()

    assert len(records) == 1
    assert records[0].template_name == "coherence_llm"
    assert records[0].version == "1.2"
    assert records[0].jinja_content == "Hello {{ name }}"
