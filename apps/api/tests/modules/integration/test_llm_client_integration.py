"""
LLM Client Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-EXT-LLM-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.ai.anthropic_client import AIService
from src.core.ai.anthropic_wrapper import AIRequest, AIResponse


class _DummySessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@dataclass
class _FakeWrapper:
    last_request: AIRequest | None = None

    async def generate(self, request: AIRequest) -> AIResponse:
        self.last_request = request
        return AIResponse(
            content='{"answer": "ok"}',
            model_used="mock-llm",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
            latency_ms=3.5,
        )


@pytest.mark.asyncio
class TestLLMClientIntegration:
    """Refers to Suite ID: TS-INT-EXT-LLM-001."""

    async def test_llm_client_runs_extraction_with_wrapper(self, monkeypatch) -> None:
        monkeypatch.setenv("C2PRO_TEST_LIGHT", "1")
        monkeypatch.setenv("C2PRO_AI_MOCK", "0")

        from src.analysis.adapters.ai import anthropic_client as client_module

        def _dummy_session(_: UUID):
            return _DummySessionContext()

        monkeypatch.setattr(client_module, "get_session_with_tenant", _dummy_session)

        wrapper = _FakeWrapper()
        tenant_id = str(uuid4())
        service = AIService(wrapper=wrapper, tenant_id=tenant_id)

        result = await service.run_extraction(
            system_prompt="System",
            user_content="User content",
        )

        assert result == {"answer": "ok"}
        assert wrapper.last_request is not None
        assert wrapper.last_request.prompt == "User content"
        assert wrapper.last_request.system_prompt == "System"
