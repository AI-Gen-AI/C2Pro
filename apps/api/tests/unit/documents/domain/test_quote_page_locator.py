"""Synthetic tests for JV1-A9; no source contract data or external provider."""

from __future__ import annotations

import pytest

from documents.domain.quote_page_locator import (
    PageSpan,
    QuotePageLocation,
    locate_quote_page,
)


def _pages(*texts: str) -> tuple[str, list[PageSpan]]:
    offset = 0
    spans: list[PageSpan] = []
    for number, text in enumerate(texts, start=1):
        spans.append(PageSpan(number, offset, offset + len(text)))
        offset += len(text)
    return "".join(texts), spans


def test_exact_quote_returns_original_offsets_and_physical_page() -> None:
    source, spans = _pages("Preamble.\n", "Supplier shall deliver all goods in 30 days. End.")
    quote = "Supplier shall deliver all goods in 30 days."
    location = locate_quote_page(quote, source_text=source, page_spans=spans)
    start = source.index(quote)
    assert location == QuotePageLocation(2, 2, start, start + len(quote))


def test_whitespace_normalization_keeps_source_offsets() -> None:
    source, spans = _pages("Supplier  shall\n\t deliver within 30 days.")
    quote = "Supplier shall deliver within 30 days."
    assert locate_quote_page(quote, source_text=source, page_spans=spans) == QuotePageLocation(
        1, 1, 0, len(source)
    )


def test_redacted_middle_has_literal_visible_anchors() -> None:
    source, spans = _pages("The purchaser shall pay EUR 120000 within thirty days.")
    location = locate_quote_page(
        "The purchaser shall pay [REDACTED] within thirty days.",
        source_text=source,
        page_spans=spans,
    )
    assert location == QuotePageLocation(1, 1, 0, len(source))


def test_two_redactions_with_independent_anchors() -> None:
    source, spans = _pages("Supplier shall deliver 42 units by Friday and issue final acceptance.")
    assert locate_quote_page(
        "Supplier shall deliver [REDACTED] by Friday [REDACTED] final acceptance.",
        source_text=source,
        page_spans=spans,
    ) == QuotePageLocation(1, 1, 0, len(source))


@pytest.mark.parametrize(
    "quote",
    ["", "   ", "[REDACTED]", "Supplier [REDACTED]", "[REDACTED] within 30 days"],
)
def test_unanchored_or_empty_quotes_fail_closed(quote: str) -> None:
    source, spans = _pages("Supplier shall deliver within 30 days.")
    assert locate_quote_page(quote, source_text=source, page_spans=spans) is None


def test_long_redaction_does_not_match_arbitrary_distant_text() -> None:
    source, spans = _pages("Supplier agrees " + ("X" * 2500) + " within thirty days")
    assert (
        locate_quote_page(
            "Supplier agrees [REDACTED] within thirty days",
            source_text=source,
            page_spans=spans,
        )
        is None
    )


def test_repeated_quote_uses_nearest_n2_offset() -> None:
    phrase = "The supplier shall remedy defects."
    source, spans = _pages(phrase + "\n", "Appendix. " + phrase)
    second = source.rindex(phrase)
    assert locate_quote_page(
        phrase, source_text=source, page_spans=spans, near_offset=second + 4
    ) == QuotePageLocation(2, 2, second, second + len(phrase))


def test_duplicate_without_n2_anchor_is_ambiguous() -> None:
    source, spans = _pages("Obligation applies.", "Obligation applies.")
    assert locate_quote_page("Obligation applies.", source_text=source, page_spans=spans) is None


def test_equidistant_duplicates_fail_closed() -> None:
    source, spans = _pages("Clause one.-----Clause one.")
    assert (
        locate_quote_page("Clause one.", source_text=source, page_spans=spans, near_offset=8)
        is None
    )


def test_cross_page_quote_reports_range_and_real_offsets() -> None:
    source, spans = _pages("The contractor shall ", "deliver all equipment.")
    quote = "shall deliver"
    begin = source.index(quote)
    assert locate_quote_page(quote, source_text=source, page_spans=spans) == QuotePageLocation(
        1, 2, begin, begin + len(quote)
    )


def test_cross_page_redacted_quote_reports_range() -> None:
    source, spans = _pages("The contractor shall provide ", "spare components within thirty days.")
    assert locate_quote_page(
        "The contractor shall [REDACTED] within thirty days.",
        source_text=source,
        page_spans=spans,
    ) == QuotePageLocation(1, 2, 0, len(source))


def test_unmapped_nonwhitespace_between_pages_fails_closed() -> None:
    source = "Alpha unmapped Beta"
    spans = [PageSpan(1, 0, 6), PageSpan(2, 15, len(source))]
    assert locate_quote_page("Alpha unmapped Beta", source_text=source, page_spans=spans) is None


def test_unmapped_quote_even_if_literal_in_source_fails_closed() -> None:
    source = "The clause exists but has no validated page."
    spans = [PageSpan(1, 0, 10)]
    assert locate_quote_page("has no validated page.", source_text=source, page_spans=spans) is None


@pytest.mark.parametrize(
    "spans",
    [
        [],
        [PageSpan(0, 0, 10)],
        [PageSpan(1, -1, 10)],
        [PageSpan(1, 0, 50)],
        [PageSpan(1, 10, 5)],
        [PageSpan(1, 0, 8), PageSpan(2, 7, 10)],
        [PageSpan(2, 0, 5), PageSpan(1, 5, 10)],
        [PageSpan(1, 0, 5), PageSpan(1, 5, 10)],
    ],
)
def test_invalid_page_maps_fail_closed(spans: list[PageSpan]) -> None:
    assert locate_quote_page("1234", source_text="1234567890", page_spans=spans) is None


def test_nonconsecutive_physical_page_range_is_not_asserted() -> None:
    source = "First page text, second page text"
    spans = [PageSpan(1, 0, 17), PageSpan(3, 17, len(source))]
    assert locate_quote_page("text, second", source_text=source, page_spans=spans) is None


def test_quote_mutation_is_not_literal_and_fails_closed() -> None:
    source, spans = _pages("Supplier shall deliver 100 items.")
    assert (
        locate_quote_page(
            "Supplier shall deliver 1000 items.",
            source_text=source,
            page_spans=spans,
        )
        is None
    )


def test_no_partial_word_substring_matches() -> None:
    source, spans = _pages("A brisket is not a risk record.")
    assert locate_quote_page("brisk", source_text=source, page_spans=spans) is None


@pytest.mark.parametrize("near_offset", [-1, 10000])
def test_invalid_anchor_fails_closed(near_offset: int) -> None:
    source, spans = _pages("Valid quoted obligation.")
    assert (
        locate_quote_page(
            "Valid quoted obligation.",
            source_text=source,
            page_spans=spans,
            near_offset=near_offset,
        )
        is None
    )


def test_unicode_offsets_are_character_offsets() -> None:
    source, spans = _pages("Condición económica: ", "pago en treinta días.")
    assert locate_quote_page(
        "económica: pago", source_text=source, page_spans=spans
    ) == QuotePageLocation(
        1, 2, source.index("económica"), source.index("económica") + len("económica: pago")
    )


def test_repeated_masked_quote_without_anchor_is_ambiguous() -> None:
    source, spans = _pages(
        "The purchaser shall pay EUR 150 within thirty days.\n",
        "The purchaser shall pay EUR 200 within thirty days.",
    )
    assert (
        locate_quote_page(
            "The purchaser shall pay [REDACTED] within thirty days.",
            source_text=source,
            page_spans=spans,
        )
        is None
    )


def test_too_many_redactions_fail_closed() -> None:
    source, spans = _pages("Alpha value and beta value and gamma amount and final action.")
    assert (
        locate_quote_page(
            "Alpha [REDACTED] beta [REDACTED] gamma [REDACTED] final action.",
            source_text=source,
            page_spans=spans,
        )
        is None
    )


@pytest.mark.parametrize(
    "page_spans",
    [
        [PageSpan(True, 0, 20)],
        [PageSpan(1, False, 20)],
        [PageSpan(1, 0, True)],
        [None],
    ],
)
def test_invalid_span_types_fail_closed(page_spans: list[PageSpan]) -> None:
    assert (
        locate_quote_page(
            "Literal source phrase",
            source_text="Literal source phrase",
            page_spans=page_spans,
        )
        is None
    )


def test_untyped_missing_input_fails_closed() -> None:
    from typing import cast

    source, spans = _pages("Literal source phrase.")
    assert locate_quote_page(cast(str, None), source_text=source, page_spans=spans) is None
    assert (
        locate_quote_page("Literal source phrase.", source_text=cast(str, None), page_spans=spans)
        is None
    )


def test_many_identical_quotes_are_not_assumed_unique() -> None:
    phrase = "Repeated obligation."
    source, spans = _pages(phrase * 5_010)
    assert locate_quote_page(phrase, source_text=source, page_spans=spans) is None
