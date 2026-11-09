"""C2Pro EPC-shaped contract tests for every OmniRoute pilot route (no network)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from src.analysis.adapters.ai.omniroute_pilot import (
    PILOT_MODELS,
    OmniRoutePilotClient,
    OmniRoutePilotError,
)

EPC_RESULT = {
    "delay_days": 31,
    "over_budget_eur": 200000,
    "evidence": ["CONTRATO-1", "CRONOGRAMA-1", "PRESUPUESTO-1"],
}
EPC_PROMPT = (
    "CONTRATO-1: fecha final 2026-09-30 y precio 1000000 EUR. "
    "CRONOGRAMA-1: fecha final 2026-10-31. "
    "PRESUPUESTO-1: total 1200000 EUR. "
    "Devuelve JSON con delay_days, over_budget_eur y evidence."
)


@pytest.mark.parametrize("provider,model", sorted(PILOT_MODELS.items()))
@pytest.mark.asyncio
async def test_each_pilot_model_routes_epc_json_without_real_network(provider: str, model: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-test-secret"
        payload = json.loads(request.content)
        assert payload["model"] == model
        assert payload["stream"] is False
        assert payload["messages"][0]["role"] == "system"
        assert "CONTRATO-1" in payload["messages"][1]["content"]
        # The mock tests compatibility with C2Pro, not live model quality.
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(EPC_RESULT)}}],
                "usage": {"prompt_tokens": 73, "completion_tokens": 54},
            },
        )

    client = OmniRoutePilotClient(
        base_url="http://127.0.0.1:20128",
        api_key="synthetic-test-secret",
        model=model,
        transport=httpx.MockTransport(handler),
    )
    result = await client.extract_json("Analiza fuentes EPC sin inventar citas", EPC_PROMPT, "n12")
    assert result == EPC_RESULT, provider


@pytest.mark.asyncio
async def test_non_json_fails_closed_and_does_not_count_as_pass() -> None:
    client = OmniRoutePilotClient(
        base_url="http://localhost:20128",
        api_key="secret-sentinel",
        model=PILOT_MODELS["gemini"],
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "Tal vez 31 días"}}]})
        ),
    )
    with pytest.raises(OmniRoutePilotError, match="invalid_json"):
        await client.extract_json("sistema", EPC_PROMPT, "n4")


@pytest.mark.asyncio
async def test_upstream_error_never_exposes_key_or_response_body() -> None:
    client = OmniRoutePilotClient(
        base_url="http://127.0.0.1:20128/v1",
        api_key="secret-sentinel",
        model=PILOT_MODELS["grok-cli"],
        transport=httpx.MockTransport(
            lambda _: httpx.Response(400, text="secret-sentinel private prompt")
        ),
    )
    with pytest.raises(OmniRoutePilotError) as exc:
        await client.extract_json("sistema", EPC_PROMPT, "n4")
    assert exc.value.status == 400
    assert "secret-sentinel" not in str(exc.value)
    assert "private prompt" not in str(exc.value)


@pytest.mark.asyncio
async def test_generate_returns_provenance_and_unknown_price_not_zero() -> None:
    client = OmniRoutePilotClient(
        base_url="http://127.0.0.1:20128",
        api_key="secret",
        model=PILOT_MODELS["openrouter"],
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "  respuesta  "}}],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 2},
                },
            )
        ),
    )
    result = await client.generate(
        SimpleNamespace(prompt="Ensayo", system_prompt="EPC", request_id="test-1", task_type="n4")
    )
    assert result.content == "respuesta"
    assert result.model_used == PILOT_MODELS["openrouter"]
    assert (result.input_tokens, result.output_tokens) == (9, 2)
    assert result.cost_usd is None
    assert result.request_id == "test-1"


def test_invalid_or_insecure_endpoint_rejected() -> None:
    with pytest.raises(ValueError):
        OmniRoutePilotClient(base_url="http://public.example:20128", api_key="secret", model=PILOT_MODELS["nvidia"])
    with pytest.raises(ValueError):
        OmniRoutePilotClient(base_url="https://user:pass@example.com", api_key="secret", model=PILOT_MODELS["nvidia"])
    with pytest.raises(ValueError):
        OmniRoutePilotClient(base_url="http://127.0.0.1:20128", api_key="secret", model="amazon-q/unverified-model")



@pytest.mark.parametrize(
    "provider,expected_budget",
    [("openrouter", 1024), ("gemini", 256), ("grok-cli", 256)],
)
@pytest.mark.asyncio
async def test_reasoning_model_has_visible_json_token_budget(
    provider: str, expected_budget: int
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == PILOT_MODELS[provider]
        assert payload["max_tokens"] == expected_budget
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(EPC_RESULT)}}]}
        )

    client = OmniRoutePilotClient(
        base_url="http://127.0.0.1:20128",
        api_key="synthetic-test-secret",
        model=PILOT_MODELS[provider],
        transport=httpx.MockTransport(handler),
    )
    result = await client.extract_json("You are an EPC analyst", EPC_PROMPT, "n4")
    assert result == EPC_RESULT
