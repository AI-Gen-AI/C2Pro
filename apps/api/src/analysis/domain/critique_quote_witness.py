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
    AMBIGUOUS = "AMBIGUOUS"
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



@dataclass(frozen=True)
class CritiqueObservation:
    """Claim remains unverified; only the exact supplied quote may be located."""

    claim: str
    source_quote: str
    witness: QuoteWitness


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
    # Zero-width lookahead catches *overlapping* occurrences as well.
    # Ordinary finditer skips valid repeated starts in e.g. "the the the".
    occurrences = re.finditer(rf"(?=({pattern}))", source_text)
    match = next(occurrences, None)
    if match is None:
        return QuoteWitness(
            status=(
                QuoteWitnessStatus.UNRESOLVED
                if source_complete
                else QuoteWitnessStatus.SOURCE_PARTIAL_UNRESOLVED
            )
        )
    if next(occurrences, None) is not None:
        # A repeated, even overlapping, span cannot be uniquely cited.
        return QuoteWitness(status=QuoteWitnessStatus.AMBIGUOUS)
    start, end = match.span(1)
    return QuoteWitness(
        status=QuoteWitnessStatus.LOCATED,
        char_start=start,
        char_end=end,
        located_text=match.group(1),
    )
