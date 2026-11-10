"""P0: exhaustive N4 input/output and N12 source integrity without provider calls."""
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
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.llm_client import LLMClient, LLMRequest


def _risk_tool() -> RiskExtractionTool:
    return RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())


def test_n4_pre_model_source_is_complete_even_for_long_annex_first_contract() -> None:
    clauses = [
        f"{n}. El contratista abonará las garantías y obligaciones de bombeo del contrato {n}."
        for n in range(1, 22)
    ]
    text = "Anexo de datos técnicos. " + "x" * 60_000 + "\n\n" + "\n\n".join(clauses)
    prepared = _risk_tool().extract_input_from_state({"document_text": text})
    assert prepared.document_text == text
    assert len(prepared.document_text) > 60_000
    assert all(clause in prepared.document_text for clause in clauses)


def test_n4_preserves_n2_anonymized_projection_without_original_fallback() -> None:
    source = "Contrato confidencial no enviado a la IA."
    redacted = "[ENTITY] deberá cumplir una condición de pago."
    prepared = _risk_tool().extract_input_from_state({
        "document_text": source,
        "anonymized_text": redacted,
        "pii_anonymization_complete": True,
    })
    assert prepared.document_text.startswith(redacted)
    assert source not in prepared.document_text


@pytest.mark.asyncio
async def test_n4_never_discards_risks_after_twentieth_candidate() -> None:
    items = [{
        "title": f"Risk {n}", "summary": f"Relevant clause {n}",
        "category": "LEGAL", "probability": "MEDIUM", "impact": "HIGH",
        "source_quote": f"This contractual obligation number {n} has an independently identifiable exposure to the project.",
    } for n in range(30)]
    response = AIResponse(content=json.dumps({"risks": items}), model_used="test",
                          input_tokens=1, output_tokens=1, cost_usd=0, latency_ms=1)
    results = await _risk_tool()._execute_impl(
        RiskExtractionInput(document_text="Source", max_risks=20),
        tenant_id=None, ai_response=response,
    )
    assert len(results) == 30
    assert {r.title for r in results} == {f"Risk {n}" for n in range(30)}


@pytest.mark.asyncio
async def test_n12_receives_complete_source_not_only_first_16000_chars() -> None:
    source = "Start." + "x" * 60_000 + "END_CONTRACT_EXCEPTION"
    fake = SimpleNamespace(run_extraction=AsyncMock(return_value={
        "status": "OK", "notes": "No issues found", "findings": [],
    }))
    result = await CritiqueExtractionService().extract(
        items=[], doc_type="contract", ai=fake,
        source_text=source, source_complete=True,
    )
    assert result.status == "OK"
    assert "END_CONTRACT_EXCEPTION" in fake.run_extraction.await_args.args[1]


@pytest.mark.asyncio
async def test_llm_max_tokens_cannot_be_accepted_or_cached(monkeypatch) -> None:
    from src.core.ai import llm_client as module

    client = object.__new__(LLMClient)
    client.circuit_breaker = None
    client.total_requests = 0
    client.total_retries = 0
    client.total_cost_usd = 0.0
    client.max_retries = 0
    client.flash_cache = SimpleNamespace(
        get=AsyncMock(return_value=None), set=AsyncMock(), size=0,
    )
    client.client = SimpleNamespace(messages=SimpleNamespace(create=MagicMock(
        return_value=SimpleNamespace(stop_reason="max_tokens")
    )))
    monkeypatch.setattr(module, "get_token_counter", lambda: SimpleNamespace(
        estimate_request=lambda **kwargs: SimpleNamespace(
            warnings=[], input_tokens=2000, estimated_output_tokens=100,
            total_cost_usd=0.1, context_usage_percent=1.0,
        )
    ))
    with pytest.raises(ValueError, match="stop_reason=max_tokens"):
        await client.generate(LLMRequest(model="claude-sonnet-4-6",
                                         messages=[{"role": "user", "content": "Analyze"}],
                                         max_tokens=8192))
    client.flash_cache.set.assert_not_awaited()
