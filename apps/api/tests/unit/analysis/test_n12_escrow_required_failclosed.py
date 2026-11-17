"""Staged N12-only escrow latch must never send an unreserved model call."""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.anthropic_client import AIService
from src.core.exceptions import AIServiceError


@pytest.mark.asyncio
@pytest.mark.parametrize("mock_mode", [False, True])
@pytest.mark.parametrize("legacy_global", [False, True])
async def test_n12_without_checkpoint_key_rejected_before_any_model(
    monkeypatch, mock_mode, legacy_global,
):
    monkeypatch.setenv("C2PRO_N12_REQUIRE_ESCROW", "1")
    if mock_mode:
        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    else:
        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    if legacy_global:
        monkeypatch.setenv("C2PRO_LEGACY_AI_ESCROW", "1")
    else:
        monkeypatch.delenv("C2PRO_LEGACY_AI_ESCROW", raising=False)
    wrapper = MagicMock()
    service = AIService(wrapper=wrapper, tenant_id=uuid4())
    with pytest.raises(AIServiceError, match="N12 escrow required"):
        await service.run_full_source_review(
            "Risk evaluation", "Full project source without checkpoint"
        )
    wrapper.generate.assert_not_called()


@pytest.mark.asyncio
async def test_empty_key_rejected_without_model_even_with_global_off(monkeypatch):
    monkeypatch.setenv("C2PRO_N12_REQUIRE_ESCROW", "1")
    monkeypatch.delenv("C2PRO_LEGACY_AI_ESCROW", raising=False)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    wrapper = MagicMock()
    service = AIService(wrapper=wrapper, tenant_id=uuid4())
    with pytest.raises(AIServiceError, match="stable call id"):
        await service.run_full_source_review(
            "Review", "Source", governed_request_id=""
        )
    wrapper.generate.assert_not_called()


@pytest.mark.asyncio
async def test_other_mock_extraction_not_blocked_by_n12_only_latch(monkeypatch):
    monkeypatch.setenv("C2PRO_N12_REQUIRE_ESCROW", "1")
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.delenv("C2PRO_LEGACY_AI_ESCROW", raising=False)
    service = AIService(wrapper=MagicMock(), tenant_id=uuid4())
    # Another extractor (N3 etc.) can still invoke its ordinary mock route.
    # This test does not establish semantic correctness of that mock response.
    result = await service.run_extraction("Classify source", "Some source")
    assert result is not None
