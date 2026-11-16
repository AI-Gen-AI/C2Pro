"""WBS 1.4: N12 may not replay the full source for repeat critiques.

This is bounded candidate-specific QA, NOT a certificate of document recall.
"""
from __future__ import annotations

import pytest

from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand,
    CritiqueExtractionUseCase,
    _n12_focal_source,
)


class RecordingAI:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {"status": "OK", "notes": "No issues found.", "findings": []}

    async def run_extraction(self, system_prompt, user_content):
        self.calls.append(user_content)
        return self.response


def make_command(source, *, retry=1, quote=None, status="VERIFIED"):
    item = {"title": "Delay damages", "confidence": 0.99}
    if quote is not None:
        item.update({"source_quote": quote, "source_quote_status": status})
    return CritiqueExtractionCommand(
        extracted_risks=[item], extracted_wbs=[],
        doc_type="contract", retry_count=retry,
        source_text=source, source_complete=True,
    )


@pytest.mark.asyncio
async def test_first_pass_preserves_full_source_contract_and_single_call():
    source = "Clause 1. Large generic contract. " * 400
    ai = RecordingAI()
    result = await CritiqueExtractionUseCase(ai=ai).execute(make_command(source, retry=0))
    assert len(ai.calls) == 1
    assert source.strip() in ai.calls[0]
    assert "SOURCE PROVIDED IN FULL" in ai.calls[0]
    assert result.status == "OK"


@pytest.mark.asyncio
async def test_retry_focal_quote_sends_bounded_span_not_full_contract():
    quote = "Contractor shall pay delay damages of 1% per week of delay."
    source = ("Ordinary project terms without relevant exceptions. " * 2000) + (
        "Clause 9.6: " + quote
    ) + (" Further unrelated annex content. " * 2500)
    ai = RecordingAI()
    result = await CritiqueExtractionUseCase(ai=ai).execute(make_command(source, quote=quote))
    assert len(ai.calls) == 1
    payload = ai.calls[0]
    assert "FOCAL EXCERPT ONLY" in payload
    assert "SOURCE PROVIDED IN FULL" not in payload
    assert quote in payload
    assert source not in payload
    assert len(payload) < 10000
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required
    assert result.retry_count == 1
    assert "document-wide recall NOT assessed" in result.critique_notes


@pytest.mark.asyncio
async def test_retry_without_source_backed_quote_never_calls_provider():
    ai = RecordingAI()
    source = "Ordinary text. " * 5000
    result = await CritiqueExtractionUseCase(ai=ai).execute(make_command(source))
    assert ai.calls == []
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required
    assert result.retry_count == 1
    assert "repeat whole-source call skipped" in result.critique_notes


@pytest.mark.asyncio
async def test_retry_rejected_quote_cannot_rehabilitate_citation_or_call_model():
    ai = RecordingAI()
    source = "Clause 7: " + "This is a real obligation with no fabricated penalty. " * 500
    quote = "This is a real obligation with no fabricated penalty."
    cmd = make_command(source, quote=quote, status="NOT_FOUND_IN_DOCUMENT")
    result = await CritiqueExtractionUseCase(ai=ai).execute(cmd)
    assert result.status == "UNASSESSED"
    assert ai.calls == []


@pytest.mark.asyncio
async def test_retry_quote_not_in_sanitized_projection_is_not_model_input():
    ai = RecordingAI()
    source = "[REDACTED] " * 3000
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        make_command(source, quote="Original unredacted personal information must not leak.")
    )
    assert ai.calls == []
    assert result.human_approval_required


@pytest.mark.asyncio
async def test_retry_small_source_skips_second_call_without_faking_completion():
    ai = RecordingAI()
    quote = "Contractor shall pay delay damages of 1% per week of delay."
    source = "Clause 9.6: " + quote
    result = await CritiqueExtractionUseCase(ai=ai).execute(make_command(source, quote=quote))
    assert ai.calls == []
    assert result.status == "UNASSESSED"
    assert result.confidence is None


def test_focal_windows_bounded_and_first_max_twelve_candidates():
    quote = "The Contractor shall deliver signed certificates at each milestone."
    source = "Filler " * 30000 + quote + " continuation " * 30000
    items = [{"source_quote": quote, "source_quote_status": "VERIFIED"}] * 100
    focused = _n12_focal_source(source, items)
    assert quote in focused
    assert len(focused) < 8000
    assert len(focused) < len(source) / 10
