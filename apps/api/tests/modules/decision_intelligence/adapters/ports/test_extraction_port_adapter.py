"""Unit tests for ExtractionPortAdapter.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.decision_intelligence.adapters.ports.extraction_port_adapter import (
    ExtractionPortAdapter,
)


def _make_wrapper_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content)


@pytest.mark.asyncio
async def test_extract_returns_empty_for_empty_chunks() -> None:
    wrapper = SimpleNamespace(generate=AsyncMock())
    adapter = ExtractionPortAdapter(wrapper=wrapper)  # type: ignore[arg-type]
    assert await adapter.extract_clauses([]) == []
    wrapper.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_parses_valid_json_payload() -> None:
    payload = json.dumps(
        [
            {
                "clause_code": "PAY-1",
                "title": "Payment terms",
                "text": "Payment within 30 days",
                "confidence": 0.91,
                "citations": ["page-1", "section-4.2"],
            }
        ]
    )
    wrapper = SimpleNamespace(generate=AsyncMock(return_value=_make_wrapper_response(payload)))
    adapter = ExtractionPortAdapter(wrapper=wrapper)  # type: ignore[arg-type]

    result = await adapter.extract_clauses(
        [{"text": "Payment within 30 days", "page": 1, "offset": 0}]
    )

    assert len(result) == 1
    clause = result[0]
    assert clause["clause_code"] == "PAY-1"
    assert clause["text"] == "Payment within 30 days"
    assert clause["confidence"] == pytest.approx(0.91)
    assert clause["metadata"]["citations"] == ["page-1", "section-4.2"]
    assert "clause_id" in clause


@pytest.mark.asyncio
async def test_extract_strips_code_fences() -> None:
    payload = "```json\n[{\"text\": \"X\", \"citations\": [\"p-1\"]}]\n```"
    wrapper = SimpleNamespace(generate=AsyncMock(return_value=_make_wrapper_response(payload)))
    adapter = ExtractionPortAdapter(wrapper=wrapper)  # type: ignore[arg-type]
    result = await adapter.extract_clauses([{"text": "X", "page": 1}])
    assert len(result) == 1
    assert result[0]["metadata"]["citations"] == ["p-1"]


@pytest.mark.asyncio
async def test_extract_injects_default_citation_when_missing() -> None:
    payload = json.dumps([{"text": "X", "citations": []}])
    wrapper = SimpleNamespace(generate=AsyncMock(return_value=_make_wrapper_response(payload)))
    adapter = ExtractionPortAdapter(wrapper=wrapper)  # type: ignore[arg-type]
    result = await adapter.extract_clauses([{"text": "X", "page": 4}])
    assert result[0]["metadata"]["citations"] == ["page-4"]


@pytest.mark.asyncio
async def test_extract_fallback_on_llm_failure() -> None:
    wrapper = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError("boom")))
    adapter = ExtractionPortAdapter(wrapper=wrapper)  # type: ignore[arg-type]
    result = await adapter.extract_clauses(
        [{"text": "Recovery clause content", "page": 2}]
    )
    assert len(result) == 1
    clause = result[0]
    assert clause["metadata"]["citations"] == ["page-2"]
    assert clause["text"].startswith("Recovery clause content")


@pytest.mark.asyncio
async def test_extract_fallback_on_invalid_json() -> None:
    wrapper = SimpleNamespace(
        generate=AsyncMock(return_value=_make_wrapper_response("no json here"))
    )
    adapter = ExtractionPortAdapter(wrapper=wrapper)  # type: ignore[arg-type]
    result = await adapter.extract_clauses([{"text": "clause", "page": 1}])
    assert len(result) == 1
    assert result[0]["metadata"]["citations"] == ["page-1"]
