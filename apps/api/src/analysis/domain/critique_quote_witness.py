"""Source-quote witnesses for AI critique (PQ-HITL-01).

Locating quoted bytes (allowing line-wrap whitespace) proves only that a
quotation was found in the supplied excerpt. It NEVER verifies the critic's
inference, asserts the completeness of a contract, or supplies page geometry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class QuoteWitnessStatus(StrEnum):
    LOCATED = "LOCATED"
    UNRESOLVED = "UNRESOLVED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_PARTIAL_UNRESOLVED = "SOURCE_PARTIAL_UNRESOLVED"


@dataclass(frozen=True)
class QuoteWitness:
    status: QuoteWitnessStatus
    char_start: int | None = None
    char_end: int | None = None
    located_text: str | None = None
    # A quote match NEVER verifies any proposition or legal conclusion.
    claim_verified: bool = False


def verify_source_quote(
    source_text: str | None,
    quote: str,
    *,
    source_complete: bool = True,
) -> QuoteWitness:
    """Return exact witness offsets or explicit uncertainty.

    A partial excerpt can support *presence* but can never prove absence.
    Preserve the raw matched substring; no guesses about page, clause or risk.
    """
    if not source_text or not source_text.strip():
        return QuoteWitness(status=QuoteWitnessStatus.SOURCE_UNAVAILABLE)

    tokens = quote.split()
    if not tokens:
        return QuoteWitness(status=QuoteWitnessStatus.UNRESOLVED)

    # Allow PDF line wrapping while preserving every literal source character.
    # All content tokens remain literal; user-controlled quote is NEVER regex.
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    match = re.search(pattern, source_text)
    if match is None:
        return QuoteWitness(
            status=(
                QuoteWitnessStatus.UNRESOLVED
                if source_complete
                else QuoteWitnessStatus.SOURCE_PARTIAL_UNRESOLVED
            )
        )
    return QuoteWitness(
        status=QuoteWitnessStatus.LOCATED,
        char_start=match.start(),
        char_end=match.end(),
        located_text=match.group(0),
    )
