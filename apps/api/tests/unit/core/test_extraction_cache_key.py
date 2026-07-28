"""Extraction cache-key regression tests.

Test Suite ID: TS-UT-QA-343-EXTRACTION-CACHE-KEY-001
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.ai.model_router import ModelTier, TaskType
from src.core.ai.service import AIRequest, AIService
from src.core.cache import (
    build_extraction_cache_fingerprint,
    build_extraction_cache_key,
)


def test_extraction_cache_key_is_stable_for_an_unchanged_extraction_contract() -> None:
    """TS-UT-QA-343-EXTRACTION-CACHE-KEY-001: equivalent requests keep cache hits."""
    fingerprint = build_extraction_cache_fingerprint(
        prompt="Extract obligations from this contract.",
        system_prompt="Return JSON only.",
        model="claude-haiku-4-20250514",
        temperature=0.0,
        max_tokens=1024,
        prompt_version="extraction-v1",
    )

    first_key = build_extraction_cache_key("document-sha", "simple_extraction", fingerprint)
    second_key = build_extraction_cache_key("document-sha", "simple_extraction", fingerprint)

    assert first_key == second_key


def test_extraction_cache_key_invalidates_for_prompt_or_model_changes() -> None:
    """TS-UT-QA-343-EXTRACTION-CACHE-KEY-001: behavior-changing inputs miss stale cache entries."""
    baseline = build_extraction_cache_key(
        "document-sha",
        "simple_extraction",
        build_extraction_cache_fingerprint(
            prompt="Extract obligations from this contract.",
            system_prompt="Return JSON only.",
            model="claude-haiku-4-20250514",
            temperature=0.0,
            max_tokens=1024,
            prompt_version="extraction-v1",
        ),
    )
    edited_prompt = build_extraction_cache_key(
        "document-sha",
        "simple_extraction",
        build_extraction_cache_fingerprint(
            prompt="Extract obligations and dates from this contract.",
            system_prompt="Return JSON only.",
            model="claude-haiku-4-20250514",
            temperature=0.0,
            max_tokens=1024,
            prompt_version="extraction-v1",
        ),
    )
    edited_model = build_extraction_cache_key(
        "document-sha",
        "simple_extraction",
        build_extraction_cache_fingerprint(
            prompt="Extract obligations from this contract.",
            system_prompt="Return JSON only.",
            model="claude-sonnet-4-20250514",
            temperature=0.0,
            max_tokens=1024,
            prompt_version="extraction-v1",
        ),
    )
    edited_temperature = build_extraction_cache_key(
        "document-sha",
        "simple_extraction",
        build_extraction_cache_fingerprint(
            prompt="Extract obligations from this contract.",
            system_prompt="Return JSON only.",
            model="claude-haiku-4-20250514",
            temperature=0.2,
            max_tokens=1024,
            prompt_version="extraction-v1",
        ),
    )

    assert baseline != edited_prompt
    assert baseline != edited_model
    assert baseline != edited_temperature


@pytest.mark.asyncio
async def test_extraction_service_uses_one_contract_fingerprint_for_cache_read_and_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UT-QA-343-EXTRACTION-CACHE-KEY-001: get and set share the versioned key contract."""
    cache_service = SimpleNamespace(
        get_extraction=AsyncMock(return_value=None),
        set_extraction=AsyncMock(),
    )
    monkeypatch.setattr("src.core.ai.service.get_cache_service", lambda: cache_service)

    service = object.__new__(AIService)
    service.budget_remaining_usd = None
    service.wrapper = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(
                content='{"clauses": []}',
                model_used="claude-haiku-4-20250514",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.01,
            )
        )
    )
    service.prompt_cache = None
    service.router = SimpleNamespace(
        estimate_cost=MagicMock(return_value=0.01),
        select_model=MagicMock(
            return_value=SimpleNamespace(
                name="claude-haiku-4-20250514",
                max_tokens=1024,
                tier=ModelTier.FLASH,
            )
        ),
    )
    service.tenant_id = None
    service._estimate_tokens = lambda _prompt: 10
    service._save_usage_log = AsyncMock()

    request = AIRequest(
        prompt="Extract obligations from this contract.",
        system_prompt="Return JSON only.",
        task_type=TaskType.SIMPLE_EXTRACTION,
        document_hash="document-sha",
        temperature=0.0,
        max_tokens=None,
        prompt_version="extraction-v1",
        use_cache=False,
    )

    await service.generate(request)

    expected_fingerprint = build_extraction_cache_fingerprint(
        prompt=request.prompt,
        system_prompt=request.system_prompt,
        model="claude-haiku-4-20250514",
        temperature=request.temperature,
        max_tokens=1024,
        prompt_version=request.prompt_version,
    )
    assert cache_service.get_extraction.await_args.args == (
        "document-sha",
        TaskType.SIMPLE_EXTRACTION.value,
        expected_fingerprint,
    )
    assert cache_service.set_extraction.await_args.args[0:3] == (
        "document-sha",
        TaskType.SIMPLE_EXTRACTION.value,
        expected_fingerprint,
    )
