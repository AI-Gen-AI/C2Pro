"""TS-AI-FLASH-002: Integration tests for LLMClient with Flash cache."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.ai.llm_client import LLMClient, LLMRequest, LLMResponse


class TestLLMClientCacheIntegration:
    """Tests for LLMClient with Flash cache integration."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(self):
        """LLMClient should return cached response on cache hit."""
        with patch("src.core.ai.llm_client.get_flash_cache_service") as mock_cache:
            mock_flash = MagicMock()
            # Return cached entry
            from src.core.ai.prompt_cache import FlashCacheEntry

            mock_flash.get = AsyncMock(
                return_value=FlashCacheEntry(
                    content="Cached response",
                    model="claude-sonnet-4-20250514",
                    input_tokens=10,
                    output_tokens=8,
                    cost_usd=0.001,
                    cached_at=9999999999.0,
                    original_execution_time_ms=100.0,
                    request_id="req-cached",
                )
            )
            mock_flash.size = 1
            mock_flash._hits = 1
            mock_cache.return_value = mock_flash

            client = LLMClient(api_key="test-key")

            # Create a request
            request = LLMRequest(
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": "Hello"}],
                temperature=0.0,
            )

            response = await client.generate(request)

            # Should return cached response
            assert response.content == "Cached response"
            assert response.cached is True
            assert response.cost_usd == 0.0  # No cost for cache hit


class TestLLMRequestBypassCache:
    """Tests for LLMRequest bypass_cache field."""

    def test_default_bypass_cache_false(self):
        """bypass_cache should default to False."""
        request = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert request.bypass_cache is False

    def test_explicit_bypass_cache_true(self):
        """Can set bypass_cache=True."""
        request = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            bypass_cache=True,
        )
        assert request.bypass_cache is True


class TestLLMResponseCached:
    """Tests for LLMResponse cached field."""

    def test_cached_default_false(self):
        """cached should default to False."""
        response = LLMResponse(
            content="Hello",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            request_id="req-1",
            execution_time_ms=100.0,
            retries=0,
        )
        assert response.cached is False

    def test_cached_can_be_set_true(self):
        """cached can be set to True."""
        response = LLMResponse(
            content="Hello",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
            request_id="req-1",
            execution_time_ms=0.0,
            retries=0,
            cached=True,
        )
        assert response.cached is True


class TestLLMRequestTools:
    """Tests for LLMRequest tools field."""

    def test_default_tools_none(self):
        """tools should default to None."""
        request = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert request.tools is None

    def test_explicit_tools(self):
        """Can set tools."""
        tools = [{"type": "function", "name": "test"}]
        request = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            tools=tools,
        )
        assert request.tools == tools