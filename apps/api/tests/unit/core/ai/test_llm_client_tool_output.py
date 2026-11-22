"""Journey V1 contracts for billable truncation and forced tool output."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
from src.core.ai.llm_client import LLMClient, LLMPartialGenerationError, LLMRequest, LLMResponse
from src.core.ai.model_router import AITaskType, ModelTier


def _bare_client() -> LLMClient:
    client = object.__new__(LLMClient)
    client.circuit_breaker = None
    client.total_requests = 0
    client.total_retries = 0
    client.total_cost_usd = 0.0
    client.max_retries = 0
    client.initial_retry_delay = 0.0
    client.backoff_multiplier = 2.0
    client.max_retry_delay = 1.0
    client.flash_cache = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
        size=0,
    )
    client._calculate_cost = lambda **_kwargs: 0.37
    return client


def _provider_response(*, stop_reason: str, content: list[object]) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(input_tokens=13, output_tokens=21),
    )


def test_max_tokens_response_exposes_billable_usage() -> None:
    """Replacing a truncation with a zero-cost error must fail this contract."""

    client = _bare_client()
    client.client = MagicMock()
    client.client.messages.create.return_value = _provider_response(
        stop_reason="max_tokens",
        content=[SimpleNamespace(type="text", text='{"partial":')],
    )
    request = LLMRequest(model="claude-haiku-test", messages=[{"role": "user", "content": "x"}])

    with pytest.raises(LLMPartialGenerationError) as raised:
        client._complete_provider_generation(
            {
                "model": request.model,
                "max_tokens": request.max_tokens,
                "messages": request.messages,
            },
            request,
        )

    assert raised.value.input_tokens == 13
    assert raised.value.output_tokens == 21
    assert raised.value.cost_usd == pytest.approx(0.37)


def test_missing_usage_on_truncated_response_rejects_without_invented_cost() -> None:
    """No provider usage means billed cost is unknown, not falsely zero."""
    client = _bare_client()
    client.client = MagicMock()
    client.client.messages.create.return_value = SimpleNamespace(
        stop_reason="max_tokens", content=[SimpleNamespace(type="text", text="partial")]
    )
    request = LLMRequest(model="claude-haiku-test", messages=[{"role": "user", "content": "x"}])
    with pytest.raises(ValueError, match="usage unavailable") as caught:
        client._complete_provider_generation(
            {
                "model": request.model,
                "max_tokens": request.max_tokens,
                "messages": request.messages,
            },
            request,
        )
    assert not isinstance(caught.value, LLMPartialGenerationError)


def test_forced_tool_payload_without_json_object_fails_closed() -> None:
    """Malformed tool-use input must not be silently treated as extracted JSON."""
    client = _bare_client()
    with pytest.raises(ValueError, match="tool_use input"):
        client._extract_content(
            SimpleNamespace(content=[SimpleNamespace(type="tool_use", input="not-an-object")])
        )


@pytest.mark.asyncio
async def test_forced_tool_use_returns_its_json_input_and_reaches_provider(monkeypatch) -> None:
    """Dropping the forced tool choice or its structured result is a transport bug."""

    from src.core.ai import llm_client as module

    client = _bare_client()
    client.client = MagicMock()
    client.client.messages.create.return_value = _provider_response(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", input={"complete": True, "items": ["A4"]})],
    )
    monkeypatch.setattr(module, "record_ai_cache_miss", lambda *_args: None)
    monkeypatch.setattr(module, "record_ai_cache_size", lambda *_args: None)
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(
                input_tokens=13,
                estimated_output_tokens=21,
                total_cost_usd=0.37,
                context_usage_percent=1.0,
                warnings=[],
            )
        ),
    )
    tools = [
        {
            "name": "emit_result",
            "description": "Emit the result",
            "input_schema": {"type": "object"},
        }
    ]
    tool_choice = {"type": "tool", "name": "emit_result"}

    response = await client.generate(
        LLMRequest(
            model="claude-haiku-test",
            messages=[{"role": "user", "content": "x"}],
            tools=tools,
            tool_choice=tool_choice,
        )
    )

    assert response.content == '{"complete": true, "items": ["A4"]}'
    assert client.client.messages.create.call_args.kwargs["tools"] == tools
    assert client.client.messages.create.call_args.kwargs["tool_choice"] == tool_choice


@pytest.mark.asyncio
async def test_wrapper_forwards_forced_tools_to_llm_client() -> None:
    """Removing wrapper forwarding would silently turn structured extraction into text mode."""

    wrapper = object.__new__(AnthropicWrapper)
    wrapper.total_requests = wrapper.cache_hits = wrapper.cache_misses = 0
    wrapper.total_cost_usd = 0.0
    wrapper.max_tokens_limit = None
    wrapper.cache_service = None
    wrapper.anonymizer_service = MagicMock()
    wrapper.anonymizer_service.anonymize_document.return_value = SimpleNamespace(
        anonymized_text="system\n<C2PRO_PROMPT_SEPARATOR>\nprompt",
        mapping={},
    )
    wrapper.model_router = MagicMock()
    wrapper.model_router.select_model_with_budget_mode.return_value = SimpleNamespace(
        name="claude-haiku-test", tier=ModelTier.FLASH, max_tokens=256
    )
    wrapper.model_router.estimate_cost.return_value = 0.01
    wrapper.llm_client = MagicMock()
    wrapper.llm_client.generate = AsyncMock(
        return_value=LLMResponse(
            content='{"complete": true}',
            model="claude-haiku-test",
            input_tokens=13,
            output_tokens=21,
            cost_usd=0.01,
            request_id="test-request",
            execution_time_ms=1.0,
            retries=0,
        )
    )
    tools = [
        {
            "name": "emit_result",
            "description": "Emit the result",
            "input_schema": {"type": "object"},
        }
    ]
    tool_choice = {"type": "tool", "name": "emit_result"}

    await wrapper.generate(
        AIRequest(
            prompt="x",
            task_type=AITaskType.CONTRACT_EXTRACTION,
            use_cache=False,
            tools=tools,
            tool_choice=tool_choice,
        )
    )

    forwarded = wrapper.llm_client.generate.await_args.args[0]
    assert forwarded.tools == tools
    assert forwarded.tool_choice == tool_choice
