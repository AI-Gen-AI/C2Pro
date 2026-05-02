"""TS-AI-FLASH-001: Tests for Flash cache layer."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.ai.prompt_cache import (
    FlashCacheEntry,
    FlashCacheService,
    build_flash_cache_key,
    should_bypass_flash_cache,
    get_flash_cache_service,
    FLASH_CACHE_TTL_SECONDS,
    FLASH_CACHE_BYPASS_TEMPERATURE,
)


class TestBuildFlashCacheKey:
    """Tests for build_flash_cache_key function."""

    def test_same_inputs_produce_same_key(self):
        """Same inputs should produce identical cache keys."""
        key1 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        key2 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        assert key1 == key2

    def test_different_model_produces_different_key(self):
        """Different models should produce different keys."""
        key1 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        key2 = build_flash_cache_key(
            model_id="claude-haiku-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        assert key1 != key2

    def test_different_temperature_key(self):
        """Different temperatures should produce different keys."""
        key1 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        key2 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.5,
        )
        assert key1 != key2

    def test_temperature_rounding(self):
        """0.3 and 0.33 should produce same key (rounded)."""
        key1 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.3,
        )
        key2 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.33,
        )
        assert key1 == key2

    def test_whitespace_equivalence(self):
        """Same messages with different whitespace should produce different keys (strict)."""
        key1 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        key2 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello "}],
            tools=None,
            temperature=0.0,
        )
        assert key1 != key2

    def test_with_tools(self):
        """Including tools should affect cache key."""
        key1 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )
        key2 = build_flash_cache_key(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=[{"type": "function", "name": "test"}],
            temperature=0.0,
        )
        assert key1 != key2


class TestShouldBypassFlashCache:
    """Tests for should_bypass_flash_cache function."""

    def test_bypass_on_flag(self):
        """Should bypass when bypass_cache=True."""
        assert should_bypass_flash_cache(
            temperature=0.0,
            bypass_cache=True,
            model="claude-sonnet-4-20250514",
        ) is True

    def test_bypass_on_high_temperature(self):
        """Should bypass when temperature > 0.3."""
        assert should_bypass_flash_cache(
            temperature=0.4,
            bypass_cache=False,
            model="claude-sonnet-4-20250514",
        ) is True

    def test_no_bypass_at_threshold(self):
        """Should NOT bypass at exactly 0.3 (within limit)."""
        assert should_bypass_flash_cache(
            temperature=0.3,
            bypass_cache=False,
            model="claude-sonnet-4-20250514",
        ) is False

    def test_bypass_on_streaming_model(self):
        """Should bypass streaming model variants."""
        assert should_bypass_flash_cache(
            temperature=0.0,
            bypass_cache=False,
            model="claude-sonnet-4-20250514-stream",
        ) is True

    def test_no_bypass_normal_case(self):
        """Should NOT bypass for normal deterministic requests."""
        assert should_bypass_flash_cache(
            temperature=0.0,
            bypass_cache=False,
            model="claude-sonnet-4-20250514",
        ) is False


class TestFlashCacheEntry:
    """Tests for FlashCacheEntry."""

    def test_is_expired_false(self):
        """New entry should not be expired."""
        entry = FlashCacheEntry(
            content="Hello",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            cached_at=1000.0,  # Old timestamp
            original_execution_time_ms=100.0,
            request_id="req-123",
        )
        with patch("time.time", return_value=1000.1):
            assert entry.is_expired() is False


class TestFlashCacheService:
    """Tests for FlashCacheService."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Cache should return stored entry on hit."""
        cache = FlashCacheService(redis_url=None)

        await cache.set(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
            content="Hello! How can I help you?",
            input_tokens=10,
            output_tokens=8,
            cost_usd=0.001,
            execution_time_ms=100.0,
            request_id="req-123",
        )

        result = await cache.get(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )

        assert result is not None
        assert result.content == "Hello! How can I help you?"
        assert cache.hits == 1
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Cache should return None on miss."""
        cache = FlashCacheService(redis_url=None)

        result = await cache.get(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
        )

        assert result is None
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_bypass_on_temperature(self):
        """Should not cache when temperature > 0.3."""
        cache = FlashCacheService(redis_url=None)

        # Set with low temp
        await cache.set(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
            content="Hello",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            execution_time_ms=100.0,
            request_id="req-1",
        )

        # Get with high temp should bypass
        result = await cache.get(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.5,  # Above threshold
        )

        # Should be miss due to bypass
        assert result is None or cache.misses >= 1

    @pytest.mark.asyncio
    async def test_bypass_on_flag(self):
        """Should not cache when bypass_cache=True in get."""
        cache = FlashCacheService(redis_url=None)

        await cache.set(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
            content="Hello",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            execution_time_ms=100.0,
            request_id="req-1",
        )

        # Get with bypass flag
        result = await cache.get(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            temperature=0.0,
            bypass_cache=True,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_size_tracking(self):
        """Cache should track size correctly."""
        cache = FlashCacheService(redis_url=None)

        assert cache.size == 0

        await cache.set(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Test 1"}],
            tools=None,
            temperature=0.0,
            content="Response 1",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            execution_time_ms=100.0,
            request_id="req-1",
        )

        assert cache.size == 1

        await cache.set(
            model_id="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Test 2"}],
            tools=None,
            temperature=0.0,
            content="Response 2",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            execution_time_ms=100.0,
            request_id="req-2",
        )

        assert cache.size == 2

    @pytest.mark.asyncio
    async def test_clear_expired(self):
        """Should clear expired entries."""
        cache = FlashCacheService(redis_url=None)

        # Manually add expired entry
        cache._memory["expired"] = FlashCacheEntry(
            content="Expired",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            cached_at=0.0,  # Very old - should be expired
            original_execution_time_ms=100.0,
            request_id="req-1",
        )

        # Add valid entry
        cache._memory["valid"] = FlashCacheEntry(
            content="Valid",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            cached_at=9999999999.0,  # Future timestamp
            original_execution_time_ms=100.0,
            request_id="req-2",
        )

        with patch("time.time", return_value=10000.0):
            evicted = await cache.clear_expired()

        assert evicted >= 1


class TestGetFlashCacheService:
    """Tests for get_flash_cache_service singleton."""

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        cache1 = get_flash_cache_service()
        cache2 = get_flash_cache_service()
        assert cache1 is cache2