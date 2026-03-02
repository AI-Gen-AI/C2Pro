"""
LLM Fallback Client - Provides primary/fallback LLM client pattern.
"""

from __future__ import annotations

import structlog
from typing import Any

logger = structlog.get_logger()


class LLMFallbackClient:
    """
    Client that falls back to a secondary LLM provider if the primary fails.
    """

    def __init__(self, primary_client: Any, fallback_client: Any) -> None:
        self.primary_client = primary_client
        self.fallback_client = fallback_client

    async def generate(self, **kwargs: Any) -> Any:
        """
        Attempts generation with primary client, falls back to secondary on failure.
        """
        try:
            result = await self.primary_client.generate(**kwargs)
            return result
        except Exception as e:
            logger.warning(
                "primary_llm_failed_falling_back",
                error=str(e),
                fallback="secondary",
            )
            result = await self.fallback_client.generate(**kwargs)
            return result
