"""Quote → page locator (interface frozen by JV1-A1; implemented by A9).

Ownership passes to lane L4 once A1 is merged.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageSpan:
    """Offsets of one page inside the parsed text (``parsed_text_page_spans``)."""

    page: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class QuotePageLocation:
    """Where a quote was found; ``page_start != page_end`` means "pp. a–b"."""

    page_start: int
    page_end: int
    start_offset: int
    end_offset: int


def locate_quote_page(
    quote: str,
    *,
    source_text: str,
    page_spans: Sequence[PageSpan],
    near_offset: int | None = None,
) -> QuotePageLocation | None:
    """Return the page(s) of ``quote`` in ``source_text`` or None if absent.

    ``near_offset`` (the N2 span start) disambiguates repeated quotes.
    """
    raise NotImplementedError("JV1-A9 implements the quote page locator")
