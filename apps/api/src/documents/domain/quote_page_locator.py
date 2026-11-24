"""Resolve an N2 quote to a physical page without inferring evidence.

This operates on source text and a known physical-page mapping. It does
not perform OCR, invent pages or verify redacted material as literal.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

_MAX_QUOTE_LENGTH = 16_384
_MAX_REDACTIONS = 2
_MAX_REDACTED_CHARS = 2_048
_MAX_MATCH_CANDIDATES = 5_000


@dataclass(frozen=True, slots=True)
class PageSpan:
    """Offsets of one page in the parsed text (parsed_text_page_spans)."""

    page: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class QuotePageLocation:
    """Physical page(s) and original character offsets for a quotation."""

    page_start: int
    page_end: int
    start_offset: int
    end_offset: int


def _normalize_with_offsets(text: str) -> tuple[str, list[int], list[int]]:
    """Collapse whitespace but preserve original character offsets."""
    normalized: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for index, character in enumerate(text):
        if character.isspace():
            if normalized and normalized[-1] == " ":
                ends[-1] = index + 1
            else:
                normalized.append(" ")
                starts.append(index)
                ends.append(index + 1)
        else:
            normalized.append(character)
            starts.append(index)
            ends.append(index + 1)
    return "".join(normalized), starts, ends


def _valid_page_map(page_spans: Sequence[PageSpan], text_length: int) -> bool:
    if not page_spans:
        return False
    previous_page = 0
    previous_end = 0
    for span in page_spans:
        if not isinstance(span, PageSpan):
            return False
        if (
            not isinstance(span.page, int)
            or isinstance(span.page, bool)
            or not isinstance(span.start_offset, int)
            or isinstance(span.start_offset, bool)
            or not isinstance(span.end_offset, int)
            or isinstance(span.end_offset, bool)
            or span.page <= previous_page
            or span.start_offset < previous_end
            or span.start_offset < 0
            or span.end_offset < span.start_offset
            or span.end_offset > text_length
        ):
            return False
        previous_page = span.page
        previous_end = span.end_offset
    return True


def _pages_for_range(
    source_text: str,
    page_spans: Sequence[PageSpan],
    begin: int,
    end: int,
) -> tuple[int, int] | None:
    """Require every matched non-whitespace character to have a page."""
    first: int | None = None
    last: int | None = None
    covered_until = begin
    for span in page_spans:
        if span.end_offset <= begin:
            continue
        if span.start_offset >= end:
            break
        left = max(begin, span.start_offset)
        right = min(end, span.end_offset)
        if left >= right:
            continue
        if source_text[covered_until:left].strip():
            return None
        if first is None:
            if left != begin:
                return None
            first = span.page
        elif last is not None and span.page != last + 1:
            return None
        last = span.page
        covered_until = right

    if first is None or last is None or covered_until != end:
        return None
    return first, last


def _quote_anchors(quote: str) -> list[str] | None:
    if not isinstance(quote, str):
        return None
    normalized = " ".join(quote.split())
    if not normalized or len(normalized) > _MAX_QUOTE_LENGTH:
        return None

    anchors = normalized.split("[REDACTED]")
    redactions = len(anchors) - 1
    if redactions > _MAX_REDACTIONS:
        return None
    if redactions:
        if any(sum(ch.isalnum() for ch in anchor) < 3 for anchor in anchors):
            return None
        if sum(ch.isalnum() for anchor in anchors for ch in anchor) < 10:
            return None
    return anchors


def _all_positions(text: str, fragment: str) -> list[int]:
    found: list[int] = []
    cursor = 0
    while (position := text.find(fragment, cursor)) >= 0:
        found.append(position)
        cursor = position + 1  # Preserve overlapping literal matches.
    return found


def _valid_word_boundaries(text: str, begin: int, end: int) -> bool:
    before_is_word = begin > 0 and (text[begin - 1].isalnum() or text[begin - 1] == "_")
    after_is_word = end < len(text) and (text[end].isalnum() or text[end] == "_")
    starts_inside_word = (text[begin].isalnum() or text[begin] == "_") and before_is_word
    ends_inside_word = (text[end - 1].isalnum() or text[end - 1] == "_") and after_is_word
    return not (starts_inside_word or ends_inside_word)


def _literal_match_ranges(text: str, anchors: list[str]) -> list[tuple[int, int]]:
    """Join exact visible anchors in bounded gaps, without wildcard regex."""
    anchor_positions = [_all_positions(text, anchor) for anchor in anchors]
    if not all(anchor_positions):
        return []

    matches: list[tuple[int, int]] = []
    for begin in anchor_positions[0]:
        endings = [begin + len(anchors[0])]
        for index, anchor in enumerate(anchors[1:], start=1):
            positions = anchor_positions[index]
            upcoming: list[int] = []
            for end in endings:
                left = bisect_left(positions, end + 1)
                right = bisect_right(positions, end + _MAX_REDACTED_CHARS)
                upcoming.extend(pos + len(anchor) for pos in positions[left:right])
                if len(upcoming) > _MAX_MATCH_CANDIDATES:
                    return []
            endings = upcoming
            if not endings:
                break
        for end in endings:
            if _valid_word_boundaries(text, begin, end):
                matches.append((begin, end))
                if len(matches) > _MAX_MATCH_CANDIDATES:
                    # More than this many matches cannot be trusted as unambiguous.
                    return []
    return matches


def locate_quote_page(
    quote: str,
    *,
    source_text: str,
    page_spans: Sequence[PageSpan],
    near_offset: int | None = None,
) -> QuotePageLocation | None:
    """Locate source offsets and physical pages, or return None.

    Only whitespace changes are tolerated in literal quotes. A
    [REDACTED] placeholder can hide a bounded segment if independent
    visible anchors match, but this never validates hidden text.
    Ambiguous citations and missing page mappings fail closed.
    """
    if not isinstance(source_text, str) or not source_text:
        return None
    if not _valid_page_map(page_spans, len(source_text)):
        return None
    if near_offset is not None and (
        not isinstance(near_offset, int)
        or isinstance(near_offset, bool)
        or near_offset < 0
        or near_offset > len(source_text)
    ):
        return None
    anchors = _quote_anchors(quote)
    if anchors is None:
        return None

    normalized, start_indices, end_indices = _normalize_with_offsets(source_text)
    candidates: list[QuotePageLocation] = []
    for norm_begin, norm_end in _literal_match_ranges(normalized, anchors):
        begin = start_indices[norm_begin]
        end = end_indices[norm_end - 1]
        pages = _pages_for_range(source_text, page_spans, begin, end)
        if pages is not None:
            candidates.append(QuotePageLocation(pages[0], pages[1], begin, end))

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if near_offset is None:
        return None
    candidates.sort(key=lambda candidate: abs(candidate.start_offset - near_offset))
    if abs(candidates[0].start_offset - near_offset) == abs(
        candidates[1].start_offset - near_offset
    ):
        return None
    return candidates[0]
