"""
Unit tests for Anthropic wrapper runtime configuration.

Test Suite ID: TS-UD-AI-CONFIG-001
"""
from __future__ import annotations


def test_get_anthropic_wrapper_uses_runtime_settings(monkeypatch) -> None:
    """Test Suite ID: TS-UD-AI-CONFIG-001."""
    from src.core.ai import anthropic_wrapper

    captured: dict[str, object] = {}

    class FakeAnthropicWrapper:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(anthropic_wrapper, "_wrapper", None)
    monkeypatch.setattr(anthropic_wrapper, "AnthropicWrapper", FakeAnthropicWrapper)
    monkeypatch.setattr(anthropic_wrapper.settings, "ai_use_cache", False)
    monkeypatch.setattr(anthropic_wrapper.settings, "ai_max_retries", 0)
    monkeypatch.setattr(anthropic_wrapper.settings, "ai_timeout_seconds", 30)
    monkeypatch.setattr(anthropic_wrapper.settings, "ai_max_tokens_output", 1024)

    wrapper = anthropic_wrapper.get_anthropic_wrapper()

    assert isinstance(wrapper, FakeAnthropicWrapper)
    assert captured == {
        "enable_cache": False,
        "enable_retry": True,
        "max_retries": 0,
        "timeout_seconds": 30,
        "max_tokens_limit": 1024,
    }
