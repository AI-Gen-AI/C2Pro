"""N4 OpenAI/Gemini adapter contract: no billable calls, only local HTTP fixtures."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from src.analysis.adapters.ai.tools.n4_external_provider import (
    N4ExternalProvider,
    N4ExternalProviderConfigurationError,
    N4ProviderConfig,
)
from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.core.ai.anthropic_wrapper import AIRequest
from src.core.ai.llm_client import LLMPartialGenerationError


class _IdentityAnonymizer:
    def anonymize_document(self, content: str) -> SimpleNamespace:
        return SimpleNamespace(anonymized_text=content, mapping={})


def _config(provider: str = "openai", cap: float = 0.50) -> N4ProviderConfig:
    return N4ProviderConfig(
        provider=provider,
        model="gpt-6-luna" if provider == "openai" else "gemini-3-flash-preview",
        api_key="FAKE_KEY_DO_NOT_SEND",
        max_output_tokens=2048,
        max_request_usd=cap,
        input_usd_per_m=4.0,
        output_usd_per_m=10.0,
    )


def _request(content: str = "The entire source document, with Section 4.3.1.") -> AIRequest:
    return AIRequest(
        prompt="CONTRACT:\n" + content,
        system_prompt="Extract every substantive risk, return JSON.",
        task_type="complex_extraction",
        metadata={"full_source_analysis": True},
    )


def _json_risk() -> str:
    return json.dumps(
        {
            "risks": [
                {
                    "category": "LEGAL",
                    "title": "NTP deadline",
                    "summary": "Owner may terminate",
                    "description": "Owner payment obligation if NTP not issued.",
                    "probability": "MEDIUM",
                    "impact": "HIGH",
                    "mitigation_suggestion": "Monitor NTP",
                    "source_quote": "If Owner has not issued the Notice to Proceed by the Outside NTP Date, this Agreement shall terminate.",
                    "source_text_snippet": "If Owner has not issued the Notice to Proceed by the Outside NTP Date, this Agreement shall terminate.",
                    "clause_ref": "4.3.1",
                }
            ]
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_external_provider_preserves_contract_and_accepts_one_complete_turn(provider: str):
    calls: list[httpx.Request] = []
    content = _json_risk()

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if provider == "openai":
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": content}]}
                    ],
                    "usage": {"input_tokens": 420, "output_tokens": 85},
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": content}]}}],
                "usageMetadata": {"promptTokenCount": 420, "candidatesTokenCount": 85},
            },
        )

    provider_client = N4ExternalProvider(
        _config(provider), transport=httpx.MockTransport(handler), anonymizer=_IdentityAnonymizer()
    )
    text = "Original section. " * 120
    answer = await provider_client.generate(_request(text))
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    if provider == "openai":
        assert body["input"][0]["content"].endswith(text)
        assert body["max_output_tokens"] == 2048
        assert body["store"] is False
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["properties"]["risks"]["items"]["properties"][
            "source_quote"
        ]
    else:
        assert body["contents"][0]["parts"][0]["text"].endswith(text)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["maxOutputTokens"] == 2048
    assert answer.continuations == 0
    assert answer.model_used == _config(provider).model
    assert json.loads(answer.content)["risks"][0]["clause_ref"] == "4.3.1"
    assert answer.cost_usd == pytest.approx((420 * 4 + 85 * 10) / 1_000_000)


@pytest.mark.asyncio
async def test_no_model_call_when_estimated_spend_exceeds_ceiling():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={})

    provider = N4ExternalProvider(
        _config(cap=0.000001),
        transport=httpx.MockTransport(handler),
        anonymizer=_IdentityAnonymizer(),
    )
    with pytest.raises(N4ExternalProviderConfigurationError, match="BUDGET_PRECHECK"):
        await provider.generate(_request("No ellipsis! " * 400))
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_truncated_vendor_response_fails_closed_with_billable_usage(provider):
    def handler(_req):
        if provider == "openai":
            return httpx.Response(
                200,
                json={
                    "status": "incomplete",
                    "output": [],
                    "usage": {"input_tokens": 400, "output_tokens": 2048},
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"finishReason": "MAX_TOKENS"}],
                "usageMetadata": {"promptTokenCount": 400, "candidatesTokenCount": 2048},
            },
        )

    external = N4ExternalProvider(
        _config(provider),
        transport=httpx.MockTransport(handler),
        anonymizer=_IdentityAnonymizer(),
    )
    with pytest.raises(LLMPartialGenerationError) as exc:
        await external.generate(_request())
    assert exc.value.input_tokens == 400
    assert exc.value.output_tokens == 2048
    assert exc.value.cost_usd > 0


def test_provider_is_opt_in_and_errors_when_disabled(monkeypatch):
    monkeypatch.setenv("C2PRO_N4_PROVIDER", "gemini")
    monkeypatch.delenv("C2PRO_N4_EXTERNAL_PROVIDER_ENABLED", raising=False)
    with pytest.raises(N4ExternalProviderConfigurationError, match="NOT_ENABLED"):
        RiskExtractionTool()
    # Explicit constructor injection continues to override the provider selection.
    assert RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())


@pytest.mark.asyncio
async def test_anon_failure_blocks_provider_network():
    def handler(req):
        pytest.fail("A failed anonymizer must block all provider calls")

    class _FailingAnonymizer:
        def anonymize_document(self, content: str):
            raise RuntimeError("N2 privacy unavailable")

    external = N4ExternalProvider(
        _config(),
        transport=httpx.MockTransport(handler),
        anonymizer=_FailingAnonymizer(),
    )
    with pytest.raises(RuntimeError, match="privacy unavailable"):
        await external.generate(_request())


@pytest.mark.asyncio
async def test_tool_retains_n4_structured_normalizer_with_external_provider():
    content = _json_risk()

    def handler(_req):
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": content}]}
                ],
                "usage": {"input_tokens": 200, "output_tokens": 140},
            },
        )

    transport = httpx.MockTransport(handler)
    provider = N4ExternalProvider(_config(), transport=transport, anonymizer=_IdentityAnonymizer())
    tool = RiskExtractionTool(anthropic_wrapper=provider, prompt_manager=object())
    result = await tool.execute(RiskExtractionInput(document_text=_json_risk()))
    assert result.success
    assert len(result.data or []) == 1
    assert result.data[0].clause_ref == "4.3.1"
