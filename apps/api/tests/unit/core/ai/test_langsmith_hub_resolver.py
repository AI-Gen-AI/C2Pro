from __future__ import annotations

from pathlib import Path

from src.core.ai.langsmith_hub import LangSmithEnvProfile, PromptHubResolver


def test_env_profile_uses_environment_scoped_variables(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("LANGCHAIN_API_KEY_STAGING", "staging-key")
    monkeypatch.setenv("LANGCHAIN_PROJECT_STAGING", "c2pro-staging-isolated")

    profile = LangSmithEnvProfile.from_runtime_env()

    assert profile.environment == "staging"
    assert profile.api_key == "staging-key"
    assert profile.project == "c2pro-staging-isolated"


def test_prompt_hub_resolver_uses_cached_prompt_on_hub_failure(monkeypatch, tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text('{"c2pro/core-extraction:latest": "cached prompt"}', encoding="utf-8")

    resolver = PromptHubResolver(cache_file=cache_file)
    monkeypatch.setattr("src.core.ai.langsmith_hub.hub.pull", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))

    prompt, source = resolver.pull_prompt(
        prompt_repo="c2pro/core-extraction",
        prompt_tag="latest",
        fallback_prompt="fallback prompt",
    )

    assert prompt == "cached prompt"
    assert source == "cache:c2pro/core-extraction:latest"


def test_prompt_hub_resolver_returns_local_fallback_when_cache_misses(monkeypatch, tmp_path: Path):
    resolver = PromptHubResolver(cache_file=tmp_path / "missing.json")
    monkeypatch.setattr("src.core.ai.langsmith_hub.hub.pull", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))

    prompt, source = resolver.pull_prompt(
        prompt_repo="c2pro/core-extraction",
        prompt_tag="variant-B",
        fallback_prompt="local fallback",
    )

    assert prompt == "local fallback"
    assert source == "fallback:local"
