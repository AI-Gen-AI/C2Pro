"""
LLM Fallback Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-EXT-LLM-002.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.analysis.adapters.ai.llm_fallback_client import FallbackAIClient
from src.analysis.ports.ai_client import IAIClient


@dataclass
class _FakeClient(IAIClient):
    response: dict | None = None
    should_fail: bool = False
    calls: int = 0

    async def extract_json(self, system_prompt: str, user_content: str, task_type: str):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("primary failed")
        return self.response


@pytest.mark.asyncio
class TestLLMFallbackIntegration:
    """Refers to Suite ID: TS-INT-EXT-LLM-002."""

    async def test_fallback_used_when_primary_fails(self) -> None:
        primary = _FakeClient(response=None, should_fail=True)
        fallback = _FakeClient(response={"ok": True})

        client = FallbackAIClient(primary=primary, fallback=fallback)
        result = await client.extract_json("system", "user", "risk")

        assert result == {"ok": True}
        assert primary.calls == 1
        assert fallback.calls == 1

    async def test_primary_used_when_successful(self) -> None:
        primary = _FakeClient(response={"primary": True})
        fallback = _FakeClient(response={"ok": True})

        client = FallbackAIClient(primary=primary, fallback=fallback)
        result = await client.extract_json("system", "user", "risk")

        assert result == {"primary": True}
        assert primary.calls == 1
        assert fallback.calls == 0
