"""Source quote location only, never semantic/legal validation (PQ-HITL-01).

A located quote can still be misinterpreted. A missing quote cannot prove
corruption, deletion, or absence of a term even with complete extracted text.
No page geometry or source trust is invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

QuoteStatus = Literal["VERIFIED_EXACT", "AMBIGUOUS", "UNVERIFIED", "SOURCE_UNAVAILABLE"]


@dataclass(frozen=True)
class QuoteCheck:
    status: QuoteStatus
    revision_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None
    page: int | None = None
    absence_proven: bool = False


def verify_source_quote(
    *,
    source_revision_id: UUID,
    source_text: str | None,
    quoted_text: str,
    source_complete: bool,
) -> QuoteCheck:
    """Verify only one literal quotation within an explicitly pinned revision.

    source_complete describes the provided text coverage, *not* whether an
    obligation actually exists in the whole contract. Missing quote is always
    UNVERIFIED and never CONTRADICTED. Repeated quotes require source locator.
    """
    if source_text is None:
        return QuoteCheck(status="SOURCE_UNAVAILABLE", revision_id=source_revision_id)
    quote = quoted_text.strip()
    if not quote:
        return QuoteCheck(status="UNVERIFIED", revision_id=source_revision_id)
    start = source_text.find(quote)
    if start < 0:
        return QuoteCheck(status="UNVERIFIED", revision_id=source_revision_id)
    if source_text.find(quote, start + 1) >= 0:
        return QuoteCheck(status="AMBIGUOUS", revision_id=source_revision_id)
    return QuoteCheck(
        status="VERIFIED_EXACT",
        revision_id=source_revision_id,
        start_offset=start,
        end_offset=start + len(quote),
    )
