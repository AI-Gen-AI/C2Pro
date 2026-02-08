"""
Fallback AI client adapter.

Refers to Suite ID: TS-INT-EXT-LLM-002.
"""

from __future__ import annotations

from src.analysis.ports.ai_client import IAIClient


class FallbackAIClient(IAIClient):
    """Attempt primary AI client, fallback on error."""

    def __init__(self, *, primary: IAIClient, fallback: IAIClient) -> None:
        self._primary = primary
        self._fallback = fallback

    async def extract_json(self, system_prompt: str, user_content: str, task_type: str):
        try:
            return await self._primary.extract_json(system_prompt, user_content, task_type)
        except Exception:
            return await self._fallback.extract_json(system_prompt, user_content, task_type)
