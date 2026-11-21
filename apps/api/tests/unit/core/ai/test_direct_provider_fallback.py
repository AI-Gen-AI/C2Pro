"""Direct-provider failover contracts with mocked HTTP; zero paid calls."""
from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import anthropic
import httpx
import pytest

from src.core.ai.anthropic_wrapper import PROMPT_SEPARATOR, AIRequest, AnthropicWrapper
from src.core.ai.direct_provider_fallback import (
    DirectRoute,
    FallbackUnavailable,
    ProviderUsageUnknown,
    approved_routes,
    fallback_after_unbilled_rejection,
    safe_initial_fallback,
)
from src.core.ai.llm_client import LLMPartialGenerationError, LLMRequest, LLMResponse
from src.core.ai.model_router import AITaskType, ModelTier


def _credit_rejection() -> anthropic.BadRequestError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(
        400,
        request=req,
        json={"error": {"message": "Your credit balance is too low to access the Anthropic API"}},
    )
    return anthropic.BadRequestError("Anthropic payment required", response=resp, body=None)


def _route(provider: str) -> DirectRoute:
    return DirectRoute(
        provider=provider,
        model="gpt-4.1" if provider == "openai" else "gemini-2.5-flash",
        context_tokens=200000,
        output_tokens=32000,
        input_usd_m=Decimal("2"),
        output_usd_m=Decimal("8"),
    )


def _request(*, source: str = "Contract content", governed: bool = True) -> LLMRequest:
    return LLMRequest(
        model="claude-sonnet-4-6",
        system="Return complete JSON only",
        messages=[{"role": "user", "content": source}],
        max_tokens=8192,
        tenant_id=uuid4(),
        request_id="deterministic-reviewed-request",
        metadata={"budgeted_legacy": governed, "fallback_reserved_usd": "1.20", "full_source_analysis": True},
    )


def _openai_success() -> dict:
    return {
        "choices": [{"finish_reason": "stop", "message": {"content": "{\"risks\":[]}"}}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 25},
    }


def _gemini_success() -> dict:
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": "{\"risks\":[]}"}]}}
        ],
        "usageMetadata": {"promptTokenCount": 1200, "candidatesTokenCount": 25, "thoughtsTokenCount": 10},
    }


@pytest.mark.asyncio
async def test_credit_rejection_falls_back_to_openai_direct_only(monkeypatch) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        assert req.headers["authorization"] == "Bearer " + ("x" * 24)
        assert req.url.host == "api.openai.com"
        request_body = json.loads(req.content)
        assert request_body["model"] == "gpt-4.1"
        assert request_body["messages"][-1]["content"] == "Contract content"
        return httpx.Response(200, json=_openai_success())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fallback_after_unbilled_rejection(
            _request(), _credit_rejection(),
            routes=[_route("openai"), _route("gemini")],
            key_lookup=lambda provider: "x" * 24,
            client=client,
        )
    assert result.model == "gpt-4.1"
    assert result.content == "{\"risks\":[]}"
    assert result.input_tokens == 1200
    assert result.output_tokens == 25
    assert result.cost_usd == pytest.approx(0.0026)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_direct_openai_429_uses_gemini_without_retrying_openai(monkeypatch) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.host)
        if req.url.host == "api.openai.com":
            return httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}})
        assert req.url.host == "generativelanguage.googleapis.com"
        assert req.headers["x-goog-api-key"] == "x" * 24
        return httpx.Response(200, json=_gemini_success())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fallback_after_unbilled_rejection(
            _request(), _credit_rejection(), routes=[_route("openai"), _route("gemini")],
            key_lookup=lambda provider: "x" * 24, client=client,
        )
    assert result.model == "gemini-2.5-flash"
    assert result.output_tokens == 35  # Includes separately billed thoughts.
    assert calls == ["api.openai.com", "generativelanguage.googleapis.com"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 503, 400])
async def test_unknown_or_invalid_provider_error_stops_before_extra_spend(monkeypatch, status) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    calls = 0
    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"error": {"message": "not proven unbilled"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderUsageUnknown):
            await fallback_after_unbilled_rejection(
                _request(), _credit_rejection(), routes=[_route("openai"), _route("gemini")],
                key_lookup=lambda provider: "x" * 24, client=client,
            )
    assert calls == 1


@pytest.mark.asyncio
async def test_billed_partial_output_never_retries_other_provider(monkeypatch) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    calls: list[str] = []
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.host)
        data = _openai_success()
        data["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=data)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMPartialGenerationError) as exc:
            await fallback_after_unbilled_rejection(
                _request(), _credit_rejection(), routes=[_route("openai"), _route("gemini")],
                key_lookup=lambda provider: "x" * 24, client=client,
            )
    assert exc.value.input_tokens == 1200
    assert exc.value.output_tokens == 25
    assert exc.value.cost_usd > 0
    assert calls == ["api.openai.com"]


@pytest.mark.asyncio
async def test_no_escrow_no_fallback_even_after_credit_rejection(monkeypatch) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    with pytest.raises(FallbackUnavailable, match="escrow"):
        await fallback_after_unbilled_rejection(
            _request(governed=False), _credit_rejection(),
            routes=[_route("openai")],
        )


@pytest.mark.asyncio
async def test_no_provider_call_if_budget_or_context_insufficient(monkeypatch) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    route = _route("openai")
    too_large = _request(source="document " * 80000)
    with pytest.raises(FallbackUnavailable):
        await fallback_after_unbilled_rejection(
            too_large, _credit_rejection(),
            routes=[route], key_lookup=lambda _: "x" * 24,
        )
    small_budget = _request()
    small_budget.metadata["fallback_reserved_usd"] = "0.0001"
    with pytest.raises(FallbackUnavailable):
        await fallback_after_unbilled_rejection(
            small_budget, _credit_rejection(),
            routes=[route], key_lookup=lambda _: "x" * 24,
        )


@pytest.mark.asyncio
async def test_all_provider_keys_absent_no_network(monkeypatch) -> None:
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    with pytest.raises(FallbackUnavailable):
        await fallback_after_unbilled_rejection(
            _request(), _credit_rejection(),
            routes=[_route("openai"), _route("gemini")],
            key_lookup=lambda _: None,
        )


def test_no_fallback_on_ambiguous_anthropic_error() -> None:
    assert safe_initial_fallback(_credit_rejection())
    assert not safe_initial_fallback(RuntimeError("timeout after send"))


def test_route_whitelist_and_validated_nonzero_prices() -> None:
    with pytest.raises(ValueError):
        approved_routes(json.dumps([{"provider": "openrouter", "model": "gpt-4.1", "context_tokens": 200000, "output_tokens": 8192, "input_usd_m": 2, "output_usd_m": 8}]))
    with pytest.raises(ValueError):
        approved_routes(json.dumps([{"provider": "openai", "model": "../../escape", "context_tokens": 200000, "output_tokens": 8192, "input_usd_m": 2, "output_usd_m": 8}]))


@pytest.mark.asyncio
async def test_anthropic_wrapper_accounts_for_actual_fallback_model_without_cache(monkeypatch) -> None:
    from src.core.ai import direct_provider_fallback as mod

    wrapper = object.__new__(AnthropicWrapper)
    wrapper.total_requests = wrapper.cache_hits = wrapper.cache_misses = 0
    wrapper.total_cost_usd = 0.0
    wrapper.max_tokens_limit = None
    wrapper.enable_cache = False
    wrapper.cache_service = None
    wrapper.anonymizer_service = MagicMock()
    wrapper.anonymizer_service.anonymize_document.return_value = SimpleNamespace(
        anonymized_text=f"safe-system{PROMPT_SEPARATOR}safe-prompt", mapping={}
    )
    wrapper.model_router = MagicMock()
    wrapper.model_router.select_model_with_budget_mode.return_value = SimpleNamespace(
        name="claude-sonnet-4-6", tier=ModelTier.STANDARD, max_tokens=8192,
    )
    wrapper.llm_client = MagicMock()
    wrapper.llm_client.generate = AsyncMock(side_effect=_credit_rejection())
    monkeypatch.setattr(mod, "fallback_after_unbilled_rejection", AsyncMock(
        return_value=LLMResponse(
            content=json.dumps({"risks": []}), model="gpt-4.1", input_tokens=1000,
            output_tokens=20, cost_usd=0.00216, request_id="request",
            execution_time_ms=4, retries=0,
        )
    ))
    response = await wrapper.generate(AIRequest(
        prompt="payload", task_type=AITaskType.COMPLEX_EXTRACTION,
        tenant_id=uuid4(), use_cache=False,
    ))
    assert response.model_used == "gpt-4.1"
    assert response.cost_usd == 0.00216
    assert wrapper.total_cost_usd == 0.00216
