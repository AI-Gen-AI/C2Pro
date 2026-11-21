"""N4 + LangExtract: independent lexical span and trust-boundary tests.

Synthetic only; no contractual ABB text, provider calls or UAT database.
"""
import pytest

from src.analysis.application.n4_langextract_evidence_pilot import (
    EvidencePilotInvalid,
    make_n4_evidence_index,
    normalize_clause,
    reconcile_n4_with_langextract,
    validate_extractions,
)
from src.analysis.domain.n4_compact_window_response import parse_n4_window_output
from src.analysis.domain.n4_source_windows import plan_n4_source_windows


SOURCE = (
    "Article 7\n"
    "The supplier pays 1% each week,\n"
    "PAGE HEADER MARKER\n"
    "calculated on the late item.\n"
    "The delay penalty is the sole remedy.\n"
)
HEADER = "PAGE HEADER MARKER"
LAYOUT = ((SOURCE.index(HEADER), SOURCE.index(HEADER) + len(HEADER)),)
PAYMENT = "The supplier pays 1% each week,"
REMEDY = "The delay penalty is the sole remedy."


def _spans():
    return validate_extractions(SOURCE, [
        {"class": "penalty", "start": SOURCE.index(PAYMENT),
         "end": SOURCE.index(PAYMENT) + len(PAYMENT), "text": PAYMENT},
        {"class": "limitation", "start": SOURCE.index(REMEDY),
         "end": SOURCE.index(REMEDY) + len(REMEDY), "text": REMEDY},
    ])


def _n4(quote):
    return {
        "window_examined": True,
        "findings": [{
            "title": "Penalties", "risk_reason": "Interpretation: schedule exposure",
            "category": "contractual", "source_quote": quote,
            "clause_ref": "7", "impact": "Delay",
        }],
        "outstanding_references": [],
    }


def test_valid_spans_preserve_original_positions_and_whitespace():
    spans = _spans()
    assert len(spans) == 2
    assert spans[0].text == SOURCE[spans[0].start:spans[0].end]
    assert spans[1].extraction_class == "limitation"
    assert normalize_clause(" a  \n b ") == "a b"


@pytest.mark.parametrize("change", [
    {"start": -1},
    {"end": 10000},
    {"text": "different clause"},
    {"start": 2},
    {"class": ""},
])
def test_misanchored_langextract_is_rejected(change):
    record = {"class": "penalty", "start": SOURCE.index(PAYMENT),
              "end": SOURCE.index(PAYMENT) + len(PAYMENT), "text": PAYMENT}
    record.update(change)
    with pytest.raises(EvidencePilotInvalid):
        validate_extractions(SOURCE, [record])


def test_index_is_non_exhaustive_and_contains_exact_unmodified_source():
    index = make_n4_evidence_index(SOURCE, _spans())
    assert PAYMENT in index
    assert REMEDY in index
    assert "NON-EXHAUSTIVE" in index
    assert "ENTIRE source window" in index
    assert "source_span" in index


def test_index_fails_instead_of_truncating():
    with pytest.raises(EvidencePilotInvalid, match="do not truncate"):
        make_n4_evidence_index(SOURCE, _spans(), max_chars=20)


def test_sidecar_can_restore_layout_reflow_but_not_canonical_quote_status():
    quote = "The supplier pays 1% each week, calculated on the late item."
    parsed = parse_n4_window_output(_n4(quote), window=plan_n4_source_windows(SOURCE)[0])
    assert parsed.proposed_findings[0]["claim"]["source_evidence_status"] == (
        "NOT_FOUND_IN_MODEL_SAFE_SOURCE"
    )
    fused = reconcile_n4_with_langextract(
        SOURCE, _n4(quote), _spans(), verified_layout_ranges=LAYOUT
    )
    claim = fused["findings"][0]
    assert claim["source_quote_status"] == "LAYOUT_REFLOW_MATCH_UNVERIFIED"
    assert claim["original_source_span"] is not None
    assert HEADER in claim["source_excerpt_exact"]
    assert claim["langextract_colocated_spans"][0]["meaning"] == "COLOCATED_TEXT_ONLY"
    assert claim["semantic_validation"] == "NOT_PERFORMED"
    assert claim["risk_review_status"] == "PROPOSED_UNASSESSED"
    assert fused["trust_state"] == "UNASSESSED"
    assert fused["coherence_score"] is None
    assert fused["hitl_generated"] is False


def test_no_layout_mask_does_not_fabricate_span():
    quote = "The supplier pays 1% each week, calculated on the late item."
    result = reconcile_n4_with_langextract(SOURCE, _n4(quote), _spans())
    assert result["findings"][0]["source_quote_status"] == "UNSUPPORTED_SOURCE_QUOTE"
    assert result["findings"][0]["original_source_span"] is None


def test_exact_source_and_whitespace_reflow_have_distinct_states():
    exact = reconcile_n4_with_langextract(SOURCE, _n4(REMEDY), _spans())
    assert exact["findings"][0]["source_quote_status"] == "EXACT_SOURCE_MATCH"
    reflow = reconcile_n4_with_langextract(
        SOURCE, _n4("The supplier pays 1% each week,\n"), _spans()
    )
    assert reflow["findings"][0]["source_quote_status"] in (
        "EXACT_SOURCE_MATCH", "WHITESPACE_REFLOW_MATCH",
    )


def test_repeated_quote_remains_ambiguous_without_arbitrary_anchor():
    repeated = "same phrase. same phrase."
    result = reconcile_n4_with_langextract(
        repeated, _n4("same phrase."), validate_extractions(repeated, [])
    )
    claim = result["findings"][0]
    assert claim["source_quote_status"] == "AMBIGUOUS_EXACT_QUOTE"
    assert claim["original_source_span"] is None


@pytest.mark.parametrize("layout", [
    ((-1, 5),), ((1, 10), (8, 20)), ((9, 7),),
    ((1, len(SOURCE) + 1),),
])
def test_invalid_page_mask_is_denied(layout):
    with pytest.raises(EvidencePilotInvalid):
        reconcile_n4_with_langextract(
            SOURCE, _n4(REMEDY), _spans(), verified_layout_ranges=layout
        )


def test_hallucinated_quote_stays_unverified_even_when_lx_has_related_evidence():
    fused = reconcile_n4_with_langextract(
        SOURCE, _n4("The supplier guarantees a zero-risk project."),
        _spans(), verified_layout_ranges=LAYOUT
    )
    claim = fused["findings"][0]
    assert claim["source_quote_status"] == "UNSUPPORTED_SOURCE_QUOTE"
    assert claim["langextract_colocated_spans"] == []
    assert fused["trust_state"] == "UNASSESSED"
