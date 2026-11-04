"""N12 must not convert unsupported model critiques into approved findings."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.analysis.domain.ai_extraction import CritiqueExtractionService
from src.analysis.domain.critique_findings import (
    format_source_bound_notes,
    source_bound_findings,
)


SOURCE = (
    "EPC-04: Defects. The Contractor shall rectify a notified defect "
    "within 14 days of written notice.\n\n"
    "EPC-05: Force Majeure. Price escalation, currency fluctuation, "
    "lack of financing and ordinary market shortages are not Force Majeure.\n\n"
    "EPC-07: Liability. Aggregate liability is capped at 100% of "
    "the Contract Price, except for fraud and wilful misconduct."
)


def _finding(ref, kind, quote, explanation):
    return {
        "clause_ref": ref,
        "issue_type": kind,
        "source_quote": quote,
        "explanation": explanation,
    }


def test_validator_rejects_invented_quote_and_wrong_clause():
    findings = [
        _finding(
            "EPC-04", "omission",
            "The Contractor shall rectify a notified defect within 14 days of written notice.",
            "Missing defect rectification obligation.",
        ),
        _finding(
            "EPC-07", "omission",
            "The Contractor shall rectify a notified defect within 14 days of written notice.",
            "Quote belongs to EPC-04, not EPC-07.",
        ),
        _finding("EPC-05", "contradiction", "Financing is Force Majeure.", "Invented statement"),
    ]
    verified = source_bound_findings(findings, source_text=SOURCE)
    assert len(verified) == 1
    assert verified[0]["clause_ref"] == "EPC-04"
    assert "14 days" in format_source_bound_notes(verified)


def test_all_three_adversarial_findings_have_real_clause_provenance():
    findings = [
        _finding(
            "EPC-04", "omission",
            "The Contractor shall rectify a notified defect within 14 days of written notice.",
            "Extraction misses the 14-day defects cure.",
        ),
        _finding(
            "EPC-07", "omission",
            "Aggregate liability is capped at 100% of the Contract Price",
            "Extraction misses the cap and fraud exception.",
        ),
        _finding(
            "EPC-05", "contradiction",
            "lack of financing and ordinary market shortages are not Force Majeure.",
            "Financial hardship is excluded and must not be described as a right to relief.",
        ),
    ]
    verified = source_bound_findings(findings, source_text=SOURCE)
    assert [x["clause_ref"] for x in verified] == ["EPC-04", "EPC-07", "EPC-05"]


@pytest.mark.asyncio
async def test_service_exposes_quoted_findings_to_existing_notes_consumer():
    payload = {
        "status": "RETRY",
        "notes": "Missing source coverage",
        "findings": [
            _finding(
                "EPC-05", "contradiction",
                "Price escalation, currency fluctuation, lack of financing "
                "and ordinary market shortages are not Force Majeure.",
                "Financing is excluded, not a right to time relief.",
            )
        ],
    }
    ai = AsyncMock()
    ai.run_extraction.return_value = payload
    result = await CritiqueExtractionService().extract(
        ai=ai, items=[], doc_type="contract", source_text=SOURCE,
    )
    assert result.status == "RETRY"
    assert "EPC-05 [contradiction]" in result.notes
    assert "Price escalation" in result.notes


@pytest.mark.asyncio
async def test_service_marks_retry_without_source_findings_unassessed():
    ai = AsyncMock()
    ai.run_extraction.return_value = {
        "status": "RETRY",
        "notes": "Missing source facts; no supporting quotes",
        "findings": [],
    }
    result = await CritiqueExtractionService().extract(
        ai=ai, items=[], doc_type="contract", source_text=SOURCE,
    )
    assert result.status == "RETRY"
    assert result.notes.startswith("N12_UNASSESSED:")


@pytest.mark.asyncio
async def test_service_rejects_ok_with_reported_errors():
    ai = AsyncMock()
    ai.run_extraction.return_value = {
        "status": "OK",
        "notes": "fine",
        "findings": [_finding("EPC-04", "omission",
                               "The Contractor shall rectify a notified defect within 14 days of written notice.",
                               "Omitted.")],
    }
    result = await CritiqueExtractionService().extract(
        ai=ai, items=[], doc_type="contract", source_text=SOURCE,
    )
    assert result.status == "RETRY"
    assert result.notes.startswith("N12_UNASSESSED:")


def test_real_ai_parser_accepts_wrapped_json_without_hiding_source():
    from src.analysis.adapters.ai.anthropic_client import AIService
    from src.core.ai.anthropic_wrapper import AnthropicWrapper

    service = AIService(wrapper=AnthropicWrapper(enable_cache=False, enable_retry=False))
    payload = service._parse_json_response(
        'Here is the structured result:\n```json\n'
        '{"status":"RETRY","notes":"Audit needed","findings":[]}\n```'
    )
    assert payload["status"] == "RETRY"
