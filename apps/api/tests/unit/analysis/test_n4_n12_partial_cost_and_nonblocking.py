"""P0 independent review regressions: no event-loop block or hidden spend."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.anthropic_client import AIService
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.llm_client import (
    LLMClient,
    LLMPartialGenerationError,
    LLMRequest,
)
from src.core.exceptions import AIServiceError


def _message(stop: str, data: str):
    return SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(text=data)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
    )


def _stream(msg):
    mock = MagicMock()
    mock.__enter__.return_value.get_final_message.return_value = msg
    return mock


def _client(messages) -> LLMClient:
    client = object.__new__(LLMClient)
    client.client = SimpleNamespace(messages=messages)
    client._calculate_cost = lambda **kwargs: (
        (kwargs["input_tokens"] * 3 + kwargs["output_tokens"] * 15) / 1_000_000
    )
    client.circuit_breaker = None
    client.max_retries = 2
    client.total_requests = 0
    client.total_retries = 0
    client.total_cost_usd = 0.0
    client.flash_cache = SimpleNamespace(get=AsyncMock(), set=AsyncMock(), size=0)
    return client


def _request() -> LLMRequest:
    return LLMRequest(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "Contract"}],
        max_tokens=128_000,
        bypass_cache=True,
        metadata={"full_source_analysis": True},
    )


@pytest.mark.asyncio
async def test_full_source_streaming_runs_off_the_async_event_loop(monkeypatch) -> None:
    from src.core.ai import llm_client as module

    main_thread = threading.get_ident()
    provider_threads = []

    def provider_stream(**_kwargs):
        provider_threads.append(threading.get_ident())
        return _stream(_message("end_turn", '{"risks": []}'))

    client = _client(SimpleNamespace(stream=MagicMock(side_effect=provider_stream)))
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(
                warnings=[],
                input_tokens=1000,
                estimated_output_tokens=500,
                total_cost_usd=0.01,
                context_usage_percent=1.0,
            ),
        ),
    )
    result = await client.generate(_request())
    assert result.content == '{"risks": []}'
    assert provider_threads and all(x != main_thread for x in provider_threads)


def test_failure_after_billed_fragment_preserves_partial_usage() -> None:
    msg = _stream(_message("max_tokens", '{"risks": ['))
    provider = SimpleNamespace(stream=MagicMock(side_effect=[msg, TimeoutError("disconnect")]))
    client = _client(provider)
    with pytest.raises(LLMPartialGenerationError) as caught:
        client._complete_provider_generation(
            {
                "model": "claude-sonnet-4-6",
                "max_tokens": 128_000,
                "messages": _request().messages,
            },
            _request(),
        )
    error = caught.value
    assert (error.input_tokens, error.output_tokens) == (1000, 200)
    assert error.cost_usd > 0
    assert isinstance(error.__cause__, TimeoutError)
    assert provider.stream.call_count == 2


@pytest.mark.asyncio
async def test_no_auto_restart_and_partial_usage_counted_on_failure(monkeypatch) -> None:
    from src.core.ai import llm_client as module

    stream = MagicMock(
        side_effect=[
            _stream(_message("max_tokens", '{"risks": [')),
            TimeoutError("disconnect"),
        ]
    )
    client = _client(SimpleNamespace(stream=stream))
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(
                warnings=[],
                input_tokens=1000,
                estimated_output_tokens=500,
                total_cost_usd=0.01,
                context_usage_percent=1.0,
            ),
        ),
    )
    with pytest.raises(LLMPartialGenerationError) as caught:
        await client.generate(_request())
    assert stream.call_count == 2  # no restart of the expensive full source
    assert client.total_cost_usd == pytest.approx(caught.value.cost_usd)
    client.flash_cache.set.assert_not_awaited()


class FakeSession:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


class FakeController:
    preflight_costs: list[float] = []
    recorded_costs: list[float] = []

    def __init__(self, _db):
        pass

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int):
        assert model == "claude-sonnet-4-6"
        return (input_tokens * 3 + output_tokens * 15) / 1_000_000

    async def check_budget_availability(self, _tenant, estimate):
        self.preflight_costs.append(estimate)

    async def track_usage(self, _tenant, actual):
        self.recorded_costs.append(actual)


def _service(monkeypatch, response=None) -> AIService:
    from src.analysis.adapters.ai import anthropic_client as module

    FakeController.preflight_costs = []
    FakeController.recorded_costs = []
    monkeypatch.setattr(module, "get_session_with_tenant", lambda _tenant: FakeSession())
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(input_tokens=5000),
        ),
    )
    fake_model = SimpleNamespace(name="claude-sonnet-4-6")
    wrapper = SimpleNamespace(
        model_router=SimpleNamespace(
            select_model_with_budget_mode=MagicMock(return_value=fake_model),
        ),
        generate=AsyncMock(
            return_value=response
            or AIResponse(
                content='{"status":"OK","findings":[],"notes":"No issues found"}',
                model_used="claude-sonnet-4-6",
                input_tokens=5000,
                output_tokens=200,
                cost_usd=0.03,
                latency_ms=1,
            )
        ),
    )
    service = AIService(wrapper=wrapper, tenant_id=uuid4())
    service._cost_controller_class = FakeController
    service._budget_exception = None
    return service


@pytest.mark.asyncio
async def test_n12_full_source_authorizes_provider_capacity_not_one_cent(monkeypatch) -> None:
    service = _service(monkeypatch)
    result = await service.run_full_source_review("Review", "Full Contract")
    assert result["status"] == "OK"
    assert len(FakeController.preflight_costs) == 1
    assert FakeController.preflight_costs[0] >= 1.92
    assert len(FakeController.recorded_costs) == 1
    assert FakeController.recorded_costs[0] > 0


@pytest.mark.asyncio
async def test_n12_billed_partial_failure_is_recorded_not_hidden(monkeypatch) -> None:
    service = _service(monkeypatch)
    service.wrapper.generate.side_effect = LLMPartialGenerationError(
        "provider disconnected",
        model="claude-sonnet-4-6",
        input_tokens=5000,
        output_tokens=20_000,
        cost_usd=0.315,
    )
    with pytest.raises(AIServiceError, match="Incomplete N12 provider output"):
        await service.run_full_source_review("Review", "Full Contract")
    assert len(FakeController.preflight_costs) == 1
    assert FakeController.recorded_costs == [pytest.approx(0.315)]
