"""Source-bound synthetic N4 proposal for the isolated P0b workflow seam.

This tests API -> Celery -> N4 -> N12 -> human approval -> N17, NOT the
accuracy of an LLM. The complete model benchmark remains a separate gate.
The caller must enforce ENVIRONMENT=test AND the explicit P0b fixture flag.
Only the public two-page sample contract can enter this adapter.
"""
from __future__ import annotations

from src.analysis.domain.risk_provenance import VERIFIED, classify_quote

_FIXTURE_SENTINEL = "SAMPLE CONSTRUCTION CONTRACT"
_FIXTURE_PRICE = "The total contract price is EUR 2,400,000"
_FIXTURE_QUOTE = "Liquidated damages of EUR 3,000 per calendar day"


def proposed_fixture_risks(document_text: str) -> list[dict[str, str]]:
    if not all(marker in document_text for marker in (
        _FIXTURE_SENTINEL, _FIXTURE_PRICE, _FIXTURE_QUOTE,
    )):
        return []
    quote, provenance = classify_quote(_FIXTURE_QUOTE, document_text)
    if provenance != VERIFIED or quote is None:
        return []
    return [{
        "title": "CI fixture: contractual delay damages",
        "description": "Synthetic source-bound proposal; NOT an AI-assessed finding.",
        "category": "schedule",
        "severity": "HIGH",
        "clause_ref": "3.2",
        "source_quote": quote,
    }]
