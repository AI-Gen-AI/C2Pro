"""TS-AI-048-051: Coverage-gate tests for core AI modules."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.core.ai.anthropic_wrapper import AIResponse as WrapperResponse
from src.core.ai.llm_client import LLMClient, LLMErrorType, LLMRequest
from src.core.ai.model_router import ModelTier, TaskType
from src.core.ai.prompt_cache import (
    CachedPromptResponse,
    FlashCacheService,
    PromptCacheService,
    build_flash_cache_key,
)
from src.core.ai.service import AIRequest, AIService
from src.core.ai.tools.base import BaseTool
from src.core.ai.tools.metadata import RetryPolicy, ToolStatus


class _CacheService:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload
        self.set_calls: list[tuple[str, dict[str, object], int]] = []

    async def get_json(self, key: str) -> dict[str, object] | None:
        return self.payload

    async def set_json(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        self.set_calls.append((key, value, ttl_seconds))


class _ToolInput(BaseModel):
    text: str


class _ToolOutput(BaseModel):
    text: str


class _DummyTool(BaseTool[_ToolInput, _ToolOutput]):
    name = "dummy_tool"
    description = "Dummy coverage tool"
    retry_policy = RetryPolicy(max_retries=1)

    def __init__(self, *, fail_once: bool = False, always_fail: bool = False) -> None:
        self.fail_once = fail_once
        self.always_fail = always_fail
        self.calls = 0
        wrapper = SimpleNamespace(generate=AsyncMock(return_value=self._response()))
        super().__init__(anthropic_wrapper=wrapper, prompt_manager=MagicMock())

    async def _execute_impl(self, input_data, tenant_id, ai_response):
        self.calls += 1
        if self.always_fail or (self.fail_once and self.calls == 1):
            raise ValueError("invalid output")
        return _ToolOutput(text=f"{input_data.text}:{ai_response.content}")

    def extract_input_from_state(self, state):
        return _ToolInput(text=state["text"])

    def inject_output_into_state(self, state, result):
        state["tool_status"] = result.status.value
        state["tool_text"] = result.data.text if result.data else None
        return state

    def _build_default_prompt(self, input_data, is_retry):
        suffix = " retry" if is_retry else ""
        return f"parse {input_data.text}{suffix}", "system"

    @staticmethod
    def _response() -> WrapperResponse:
        return WrapperResponse(
            content="ok",
            model_used="claude-haiku-4",
            input_tokens=11,
            output_tokens=7,
            cost_usd=0.001,
            latency_ms=12.0,
        )


def test_llm_client_helpers_classify_retry_cost_and_statistics() -> None:
    """TS-AI-048-001: Cover LLM client helper behavior without external API calls."""
    client = object.__new__(LLMClient)
    client.initial_retry_delay = 1.0
    client.backoff_multiplier = 2.0
    client.max_retry_delay = 5.0
    client.total_requests = 4
    client.total_retries = 2
    client.total_cost_usd = 1.234
    client.circuit_breaker = SimpleNamespace(state="closed", failure_count=1)
    client.model_router = MagicMock()
    fallback_model = SimpleNamespace(name="claude-sonnet-4", tier=ModelTier.STANDARD)
    client.model_router.get_model_by_name.return_value = None
    client.model_router.get_model_by_tier.return_value = fallback_model
    client.model_router.estimate_cost.return_value = 0.123456

    assert client._classify_error(RuntimeError("boom")) == LLMErrorType.UNKNOWN
    assert client._should_retry(LLMErrorType.TIMEOUT) is True
    assert client._should_retry(LLMErrorType.AUTHENTICATION) is False
    assert 0.8 <= client._calculate_retry_delay(0, LLMErrorType.CONNECTION) <= 1.2
    assert 1.6 <= client._calculate_retry_delay(0, LLMErrorType.RATE_LIMIT) <= 2.4
    assert client._calculate_cost("unknown-sonnet", 100, 20) == pytest.approx(0.123456)
    assert client.get_statistics()["avg_retries_per_request"] == 0.5


@pytest.mark.asyncio
async def test_llm_client_cached_generation_short_circuits_api(monkeypatch) -> None:
    """TS-AI-048-002: Cover LLM cache-hit path and cache metrics."""
    cache_entry = SimpleNamespace(
        content="cached",
        model="claude-haiku-4",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.002,
        request_id="cached-req",
    )
    client = object.__new__(LLMClient)
    client.circuit_breaker = None
    client.total_requests = 0
    client.flash_cache = SimpleNamespace(
        _hits=0,
        size=1,
        get=AsyncMock(return_value=cache_entry),
    )

    monkeypatch.setattr("src.core.ai.llm_client.record_ai_cache_hit", lambda *args: None)
    monkeypatch.setattr("src.core.ai.llm_client.record_ai_cache_size", lambda *args: None)

    response = await client.generate(
        LLMRequest(
            model="claude-haiku-4",
            messages=[{"role": "user", "content": "hello"}],
            tenant_id=uuid4(),
        )
    )

    assert response.cached is True
    assert response.content == "cached"
    assert response.cost_usd == 0.0
    assert client.total_requests == 1


@pytest.mark.asyncio
async def test_llm_client_forwards_tools_to_provider(monkeypatch) -> None:
    """TS-AI-048-003: provider calls preserve Anthropic tool-use payloads."""
    client = object.__new__(LLMClient)
    client.circuit_breaker = None
    client.total_requests = 0
    client.total_retries = 0
    client.total_cost_usd = 0.0
    client.max_retries = 0
    client.flash_cache = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
        size=0,
    )
    client.client = MagicMock()
    client.client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=SimpleNamespace(input_tokens=2, output_tokens=1),
    )
    client._calculate_cost = lambda **_kwargs: 0.01

    monkeypatch.setattr("src.core.ai.llm_client.record_ai_cache_miss", lambda *args: None)
    monkeypatch.setattr("src.core.ai.llm_client.record_ai_cache_size", lambda *args: None)
    monkeypatch.setattr(
        "src.core.ai.llm_client.get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(
                input_tokens=2,
                estimated_output_tokens=1,
                total_cost_usd=0.01,
                context_usage_percent=0.0,
                warnings=[],
            )
        ),
    )
    tools = [{"name": "lookup_clause", "description": "Find a clause", "input_schema": {}}]

    await client.generate(
        LLMRequest(
            model="claude-haiku-test",
            messages=[{"role": "user", "content": "Find the clause."}],
            tools=tools,
        )
    )

    assert client.client.messages.create.call_args.kwargs["tools"] == tools


@pytest.mark.asyncio
async def test_prompt_cache_hit_expired_decode_and_invalidate_paths(monkeypatch) -> None:
    """TS-AI-049-001: Cover prompt-cache hit, expiry, decode failure, set, and invalidation."""
    fresh = CachedPromptResponse(
        content="fresh",
        model="claude-haiku-4",
        input_tokens=1,
        output_tokens=2,
        cost_usd=0.01,
        cached_at=9999999999.0,
        original_execution_time_ms=3.0,
    )
    cache = PromptCacheService(_CacheService(fresh.to_dict()))
    monkeypatch.setattr("src.core.ai.prompt_cache.record_cache_hit", lambda *args: None)
    monkeypatch.setattr("src.core.ai.prompt_cache.record_cache_miss", lambda *args: None)

    assert (await cache.get_cached_response("p", model="m")).content == "fresh"
    await cache.set_cached_response(
        prompt="p",
        response_content="r",
        model="m",
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.1,
        execution_time_ms=2.0,
    )
    assert cache.cache_service.set_calls
    assert await cache.invalidate_cache("p", model="m") is True

    expired_payload = fresh.to_dict()
    expired_payload["cached_at"] = 0.0
    assert await PromptCacheService(_CacheService(expired_payload)).get_cached_response("p") is None
    assert (
        await PromptCacheService(_CacheService({"bad": "payload"})).get_cached_response("p") is None
    )


@pytest.mark.asyncio
async def test_flash_cache_memory_redis_and_bypass_paths(monkeypatch) -> None:
    """TS-AI-049-002: Cover flash-cache keying, bypass, memory, Redis, expiry, and close."""
    monkeypatch.setattr("src.core.ai.prompt_cache.record_cache_hit", lambda *args: None)
    messages = [{"role": "user", "content": "hello"}]
    key = build_flash_cache_key("claude-haiku-4", None, messages, None, 0.0)
    service = FlashCacheService()

    await service.set(
        model_id="claude-haiku-4",
        system_prompt=None,
        messages=messages,
        tools=None,
        temperature=0.0,
        content="answer",
        input_tokens=2,
        output_tokens=3,
        cost_usd=0.01,
        execution_time_ms=5.0,
        request_id="req",
    )
    assert key in service._memory
    assert (await service.get("claude-haiku-4", None, messages, None, 0.0)).content == "answer"
    assert await service.get("claude-haiku-4", None, messages, None, 0.9) is None

    service._memory[key].cached_at = 0.0
    assert await service.clear_expired() == 1

    service._memory = {}
    redis_entry = {
        "content": "redis",
        "model": "claude-haiku-4",
        "input_tokens": 1,
        "output_tokens": 1,
        "cost_usd": 0.0,
        "cached_at": 9999999999.0,
        "original_execution_time_ms": 1.0,
        "request_id": "redis-req",
    }
    service._redis = SimpleNamespace(
        get=AsyncMock(return_value=json.dumps(redis_entry)),
        close=AsyncMock(),
    )
    assert (await service.get("claude-haiku-4", None, messages, None, 0.0)).content == "redis"
    await service.close()
    service._redis.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_ai_service_cache_budget_json_and_batch_paths(monkeypatch) -> None:
    """TS-AI-050-001: Cover AIService cache, budget, JSON parsing, and batch helpers."""
    tenant_id = uuid4()
    service = object.__new__(AIService)
    service.tenant_id = tenant_id
    service.budget_remaining_usd = 0.001
    service.prompt_cache = SimpleNamespace(
        enabled=True,
        get_cached_response=AsyncMock(
            return_value=SimpleNamespace(
                content="cached",
                model="claude-haiku-4",
                input_tokens=4,
                output_tokens=2,
                cost_usd=0.02,
                original_execution_time_ms=20.0,
                get_age_seconds=lambda: 1.0,
            )
        ),
    )
    service.router = SimpleNamespace(
        select_model=MagicMock(return_value=SimpleNamespace(name="claude-haiku-4", max_tokens=100)),
        estimate_cost=MagicMock(return_value=1.0),
    )
    service._estimate_tokens = lambda text: 12

    cached = await service.generate(AIRequest(prompt="hello", task_type=TaskType.SIMPLE_EXTRACTION))
    assert cached.cached is True
    assert cached.cost_usd == 0.0

    service.prompt_cache.enabled = False
    monkeypatch.setattr("src.core.ai.service.get_cache_service", lambda: None)
    with pytest.raises(ValueError, match="Insufficient budget"):
        await service.generate(AIRequest(prompt="expensive", task_type=TaskType.COMPLEX_EXTRACTION))

    assert service._parse_json_response('prefix {"a": 1} suffix') == {"a": 1}
    assert service._parse_json_response("```json\n[1, 2]\n```") == [1, 2]
    with pytest.raises(Exception, match="No JSON block|Failed to parse"):
        service._parse_json_response("not json")

    service.generate = AsyncMock(side_effect=["a", "b"])
    assert await service.generate_batch([MagicMock(), MagicMock()]) == ["a", "b"]


@pytest.mark.asyncio
async def test_ai_service_delegates_uncached_generation_to_pii_wrapper(monkeypatch) -> None:
    """TS-AI-050-002: legacy service calls the PII-safe wrapper, never a raw SDK client."""
    tenant_id = uuid4()
    service = object.__new__(AIService)
    service.tenant_id = tenant_id
    service.budget_remaining_usd = None
    service.prompt_cache = SimpleNamespace(enabled=False)
    service.router = SimpleNamespace(
        select_model=MagicMock(return_value=SimpleNamespace(name="claude-haiku-test", max_tokens=100)),
        estimate_cost=MagicMock(return_value=0.01),
    )
    service.usage_logger = SimpleNamespace(log_success=AsyncMock())
    service.wrapper = SimpleNamespace(
        generate=AsyncMock(
            return_value=WrapperResponse(
                content='{"status": "ok"}',
                model_used="claude-haiku-test",
                input_tokens=2,
                output_tokens=1,
                cost_usd=0.01,
                latency_ms=3.0,
            )
        )
    )
    monkeypatch.setattr("src.core.ai.service.get_cache_service", lambda: None)

    response = await service.generate(
        AIRequest(prompt="Contact alice@example.com", task_type=TaskType.SIMPLE_EXTRACTION)
    )

    assert response.content == '{"status": "ok"}'
    wrapper_request = service.wrapper.generate.await_args.args[0]
    assert wrapper_request.tenant_id == tenant_id
    assert wrapper_request.bypass_anonymization is False


@pytest.mark.asyncio
async def test_base_tool_success_retry_failure_and_state_call() -> None:
    """TS-AI-051-001: Cover BaseTool execution, retry, failure result, and graph call path."""
    tenant_id = uuid4()
    success = await _DummyTool().execute(_ToolInput(text="ok"), tenant_id=tenant_id)
    assert success.status is ToolStatus.SUCCESS
    assert success.data.text == "ok:ok"
    assert success.input_tokens == 11

    retried = await _DummyTool(fail_once=True).execute(
        _ToolInput(text="retry"), tenant_id=tenant_id
    )
    assert retried.success is True
    assert retried.retries == 1

    failed = await _DummyTool(always_fail=True).execute(_ToolInput(text="bad"), tenant_id=tenant_id)
    assert failed.success is False
    assert failed.status is ToolStatus.FAILED
    assert failed.error_type == "ToolValidationError"

    state = {"tenant_id": str(tenant_id), "text": "state", "messages": []}
    updated = await _DummyTool()(state)
    assert updated["tool_status"] == "success"
    assert updated["messages"][-1].content == "Tool 'dummy_tool' executed: success"
