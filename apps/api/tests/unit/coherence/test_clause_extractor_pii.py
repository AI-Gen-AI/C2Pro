"""TS-SEC-CLAUSE-PII-001: Clause extraction must traverse the PII-safe LLM wrapper."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.coherence.extraction import clause_extractor
from src.core.ai.anthropic_wrapper import AnthropicWrapper
from src.core.ai.llm_client import LLMResponse
from src.core.ai.model_router import ModelTier
from src.core.privacy.anonymizer import AnonymizedResult


@pytest.mark.asyncio
async def test_clause_extractor_anonymizes_clause_before_llm_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-SEC-CLAUSE-PII-001: raw clause PII must never reach the LLM transport."""
    wrapper = object.__new__(AnthropicWrapper)
    wrapper.total_requests = 0
    wrapper.cache_hits = 0
    wrapper.cache_misses = 0
    wrapper.total_cost_usd = 0.0
    wrapper.max_tokens_limit = None
    wrapper.cache_service = None

    anonymizer = MagicMock()
    anonymizer.anonymize_document.side_effect = lambda text: AnonymizedResult(
        anonymized_text=text.replace("alice@example.com", "<EMAIL_ADDRESS_1>"),
        mapping={"<EMAIL_ADDRESS_1>": "alice@example.com"},
    )
    wrapper.anonymizer_service = anonymizer

    model = SimpleNamespace(name="claude-haiku-test", tier=ModelTier.FLASH)
    wrapper.model_router = MagicMock()
    wrapper.model_router.select_model_with_budget_mode.return_value = model
    wrapper.model_router.estimate_cost.return_value = 0.0
    wrapper.llm_client = MagicMock()
    wrapper.llm_client.generate = AsyncMock(
        return_value=LLMResponse(
            content='{"payment_term_days": 30}',
            model="claude-haiku-test",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
            request_id="test-request",
            execution_time_ms=1.0,
            retries=0,
        )
    )

    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(clause_extractor, "get_anthropic_wrapper", lambda: wrapper)

    extracted = await clause_extractor._call_llm("Contact alice@example.com for payment terms.")

    assert extracted == {"payment_term_days": 30}
    anonymizer.anonymize_document.assert_called_once()
    sent_request = wrapper.llm_client.generate.await_args.args[0]
    assert "alice@example.com" not in sent_request.messages[0]["content"]
    assert "<EMAIL_ADDRESS_1>" in sent_request.messages[0]["content"]
