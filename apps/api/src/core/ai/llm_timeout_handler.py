"""
TS-E2E-ERR-TIM-001

Timeout wrapper for LLM calls with fallback status response.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol


class _LLMClientProtocol(Protocol):
    async def generate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        ...


class LLMTimeoutService:
    """Minimal timeout/fallback service used by resilience test contracts."""

    def __init__(self, llm_client: _LLMClientProtocol, timeout_seconds: int = 30) -> None:
        self._llm_client = llm_client
        self._timeout_seconds = timeout_seconds

    async def generate_with_fallback(self, prompt: str) -> dict[str, Any]:
        try:
            result = await asyncio.wait_for(
                self._llm_client.generate(prompt=prompt),
                timeout=self._timeout_seconds,
            )
            if isinstance(result, dict):
                return {"status": "ok", **result}
            return {"status": "ok", "result": result}
        except TimeoutError:
            return {"status": "fallback_retry"}
