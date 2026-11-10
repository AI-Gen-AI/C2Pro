"""P0: provider-native resources and complete N4/N12 outputs; offline only."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.analysis.domain.ai_extraction import CritiqueExtractionService
from src.core.ai.anthropic_wrapper import AIRequest, AIResponse, AnthropicWrapper
from src.core.ai.llm_client import LLMClient, LLMRequest, LLMResponse
from src.core.ai.model_capabilities import full_document_capacity
from src.core.ai.model_router import AITaskType, ModelConfig, ModelTier


def _msg(stop: str, text: str, i: int = 500, o: int = 150) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=i, output_tokens=o),
    )


def _stream(message: SimpleNamespace) -> MagicMock:
    mock = MagicMock()
    mock.__enter__.return_value.get_final_message.return_value = message
    return mock


def _client(messages: SimpleNamespace) -> LLMClient:
    client = object.__new__(LLMClient)
    client.client = SimpleNamespace(messages=messages)
    client._calculate_cost = lambda **_kwargs: 0.01  # type: ignore[method-assign]
    return client


def _api_kwargs() -> dict:
    return {
        "model": "claude-sonnet-4-6",
        "max_tokens": 128_000,
        "messages": [{"role": "user", "content": "The full EPC contract"}],
        "system": "Return one JSON object",
        "temperature": 0.0,
    }


def test_provider_verified_capacity_not_historic_8192_cap() -> None:
    assert full_document_capacity("claude-sonnet-4-6") == (1_000_000, 128_000)
    with pytest.raises(ValueError, match="not verified"):
        full_document_capacity("unverified-provider-model")


def test_streaming_for_extended_output_and_natural_completion() -> None:
    messages = SimpleNamespace(
        stream=MagicMock(return_value=_stream(_msg("end_turn", '{"risks": []}'))),
        create=MagicMock(),
    )
    client = _client(messages)
    response, content, i, o, n = client._complete_provider_generation(
        _api_kwargs(),
        LLMRequest(
            model="claude-sonnet-4-6",
            max_tokens=128_000,
            messages=_api_kwargs()["messages"],
            metadata={"full_source_analysis": True},
        ),
    )
    assert response.stop_reason == "end_turn"
    assert json.loads(content) == {"risks": []}
    assert (i, o, n) == (500, 150, 0)
    messages.create.assert_not_called()
    assert messages.stream.call_args.kwargs["max_tokens"] == 128_000


def test_streamed_max_tokens_continues_without_restarting_or_dropping_json() -> None:
    messages = SimpleNamespace(
        stream=MagicMock(
            side_effect=[
                _stream(_msg("max_tokens", '{"risks": [')),
                _stream(_msg("end_turn", "]}")),
            ]
        ),
        create=MagicMock(),
    )
    client = _client(messages)
    response, content, i, o, n = client._complete_provider_generation(
        _api_kwargs(),
        LLMRequest(
            model="claude-sonnet-4-6",
            messages=_api_kwargs()["messages"],
            max_tokens=128_000,
            metadata={"full_source_analysis": True},
        ),
    )
    assert response.stop_reason == "end_turn"
    assert json.loads(content) == {"risks": []}
    assert (i, o, n) == (1000, 300, 1)
    assert messages.stream.call_count == 2
    second_messages = messages.stream.call_args.kwargs["messages"]
    assert second_messages[0]["content"] == "The full EPC contract"
    assert second_messages[1] == {"role": "assistant", "content": '{"risks": ['}
    assert "Continue exactly" in second_messages[2]["content"]


def test_context_exhausted_is_explicit_failure_not_fabricated_completion() -> None:
    messages = SimpleNamespace(
        stream=MagicMock(return_value=_stream(_msg("max_tokens", '{"risks":[', i=999_999, o=10))),
        create=MagicMock(),
    )
    with pytest.raises(ValueError, match="provider context exhausted"):
        _client(messages)._complete_provider_generation(
            _api_kwargs(),
            LLMRequest(
                model="claude-sonnet-4-6",
                messages=_api_kwargs()["messages"],
                max_tokens=128_000,
                metadata={"full_source_analysis": True},
            ),
        )
    assert messages.stream.call_count == 1


@pytest.mark.asyncio
async def test_n4_uses_full_source_flag_and_disables_answer_cache() -> None:
    wrapper = SimpleNamespace(
        generate=AsyncMock(
            return_value=AIResponse(
                content='{"risks": []}',
                model_used="claude-sonnet-4-6",
                input_tokens=100,
                output_tokens=20,
                cost_usd=0,
                latency_ms=1,
            )
        )
    )
    tool = RiskExtractionTool(anthropic_wrapper=wrapper, prompt_manager=object())
    result = await tool.execute(RiskExtractionInput(document_text="All text retained."))
    assert result.success
    request = wrapper.generate.await_args.args[0]
    assert request.metadata["full_source_analysis"] is True
    assert request.use_cache is False
    assert "All text retained" in request.prompt


@pytest.mark.asyncio
async def test_n4_continued_malformed_json_is_rejected_without_salvage() -> None:
    tool = RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    response = AIResponse(
        content='{"risks": []}{"risks": []}',
        model_used="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0,
        latency_ms=1,
        continuations=1,
    )
    with pytest.raises(ValueError, match="not one complete JSON"):
        await tool._execute_impl(
            RiskExtractionInput(document_text="Document"),
            None,
            response,
        )


@pytest.mark.asyncio
async def test_wrapper_full_source_bypasses_8192_limit_and_legacy_cache() -> None:
    wrapper = object.__new__(AnthropicWrapper)
    wrapper.total_requests = 0
    wrapper.total_cost_usd = 0
    wrapper.max_tokens_limit = 8192
    wrapper.cache_service = None
    model = ModelConfig(
        name="claude-sonnet-4-6",
        tier=ModelTier.STANDARD,
        cost_per_1m_input=3,
        cost_per_1m_output=15,
        max_tokens=8192,
        speed_factor=1.0,
        recommended_for=[],
    )
    wrapper.model_router = SimpleNamespace(
        select_model_with_budget_mode=MagicMock(return_value=model),
        estimate_cost=lambda **_kwargs: 0.01,
    )
    wrapper.llm_client = SimpleNamespace(
        generate=AsyncMock(
            return_value=LLMResponse(
                content='{"risks": []}',
                model="claude-sonnet-4-6",
                input_tokens=100,
                output_tokens=30,
                cost_usd=0.01,
                request_id="test",
                execution_time_ms=4.0,
                retries=0,
            )
        )
    )
    result = await wrapper.generate(
        AIRequest(
            task_type=AITaskType.COMPLEX_EXTRACTION,
            prompt="All source content",
            use_cache=False,
            bypass_anonymization=True,
            metadata={"full_source_analysis": True},
        )
    )
    sent = wrapper.llm_client.generate.await_args.args[0]
    assert sent.max_tokens == 128_000
    assert sent.bypass_cache is True
    assert result.content == '{"risks": []}'


@pytest.mark.asyncio
async def test_n12_uses_full_source_capability_when_adapter_supports_it() -> None:
    class FullReview:
        def __init__(self):
            self.run_extraction = AsyncMock()
            self.full_review_mock = AsyncMock(
                return_value={
                    "status": "OK",
                    "findings": [],
                    "notes": "No issues found",
                }
            )

        async def run_full_source_review(self, system: str, content: str):
            return await self.full_review_mock(system, content)

    source = "First" + "x" * 75_000 + "FINAL_EXCEPTION"
    adapter = FullReview()
    result = await CritiqueExtractionService().extract(
        items=[],
        doc_type="contract",
        ai=adapter,
        source_text=source,
        source_complete=True,
    )
    assert result.status == "OK"
    adapter.run_extraction.assert_not_awaited()
    assert "FINAL_EXCEPTION" in adapter.full_review_mock.await_args.args[1]


@pytest.mark.asyncio
async def test_n4_full_source_fails_closed_if_one_generated_risk_is_invalid() -> None:
    tool = RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    valid = {
        "title": "Completion delay",
        "summary": "Contractor delay liability",
        "category": "SCHEDULE",
        "probability": "MEDIUM",
        "impact": "HIGH",
    }
    invalid = {"title": "Unrecognized model candidate", "category": "UNEXPECTED"}
    response = AIResponse(
        content=json.dumps({"risks": [valid, invalid]}),
        model_used="claude-sonnet-4-6",
        input_tokens=120,
        output_tokens=50,
        cost_usd=0,
        latency_ms=1,
    )
    strict_input = tool.extract_input_from_state({"document_text": "All EPC clauses"})
    assert strict_input.strict_completeness is True
    with pytest.raises(ValueError, match="2 candidates, 1 normalized"):
        await tool._execute_impl(strict_input, None, response)


@pytest.mark.asyncio
async def test_n4_full_source_fails_if_model_array_contains_non_object_item() -> None:
    tool = RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    response = AIResponse(
        content=json.dumps(
            {
                "risks": [
                    {
                        "title": "Contract deadline",
                        "category": "SCHEDULE",
                        "summary": "Deadline exposure",
                        "probability": "MEDIUM",
                        "impact": "HIGH",
                    },
                    "not a risk object",
                ]
            }
        ),
        model_used="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=40,
        cost_usd=0,
        latency_ms=1,
    )
    with pytest.raises(ValueError, match="2 model items, 1 structured candidates"):
        await tool._execute_impl(
            tool.extract_input_from_state({"document_text": "Original source"}),
            None,
            response,
        )


@pytest.mark.asyncio
async def test_full_source_end_to_end_client_accumulates_usage_without_flash_cache(
    monkeypatch,
) -> None:
    from src.core.ai import llm_client as module

    client = _client(
        SimpleNamespace(
            stream=MagicMock(
                side_effect=[
                    _stream(_msg("max_tokens", '{"risks": [')),
                    _stream(_msg("end_turn", "]}")),
                ]
            ),
            create=MagicMock(),
        )
    )
    client.circuit_breaker = None
    client.max_retries = 0
    client.total_requests = 0
    client.total_retries = 0
    client.total_cost_usd = 0.0
    client.flash_cache = SimpleNamespace(
        get=AsyncMock(),
        set=AsyncMock(),
        size=0,
    )
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **kwargs: SimpleNamespace(
                warnings=[],
                input_tokens=1000,
                estimated_output_tokens=100,
                total_cost_usd=0.01,
                context_usage_percent=1.0,
            )
        ),
    )
    result = await client.generate(
        LLMRequest(
            model="claude-sonnet-4-6",
            messages=_api_kwargs()["messages"],
            max_tokens=128_000,
            bypass_cache=True,
            metadata={"full_source_analysis": True},
        )
    )
    assert json.loads(result.content) == {"risks": []}
    assert result.continuations == 1
    assert (result.input_tokens, result.output_tokens) == (1000, 300)
    client.flash_cache.get.assert_not_awaited()
    client.flash_cache.set.assert_not_awaited()
    assert client.client.messages.stream.call_count == 2
