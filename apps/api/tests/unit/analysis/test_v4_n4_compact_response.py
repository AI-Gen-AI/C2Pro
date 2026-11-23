"""WBS 2.3/2.4: compact, lossless provider response with honest provenance."""
from __future__ import annotations

import json

import pytest

from src.analysis.domain.n4_compact_window_response import (
    N4WindowContractError,
    n4_window_source_message,
    parse_n4_window_output,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows

CLAUSE = (
    "9.6 The contractor shall provide the equipment by 30 June, "
    "subject to the extension under clause 13."
)


def _window(source=CLAUSE):
    return plan_n4_source_windows(
        source, revision_id="revision-1", max_context_chars=1200, overlap_chars=80,
    )[0]


def _finding(quote=CLAUSE, **overrides):
    return {
        "title": "Delivery obligation",
        "category": "schedule",
        "risk_reason": "A delay may affect contractual delivery.",
        "source_quote": quote,
        "clause_ref": "9.6",
        "impact": "Delivery delay",
        **overrides,
    }


def _payload(findings=None, *, examined=True, refs=None):
    return {
        "window_examined": examined,
        "findings": [_finding()] if findings is None else findings,
        "outstanding_references": [] if refs is None else refs,
    }


def test_one_exact_quote_yields_projection_only_not_original_file_attestation():
    w = _window()
    parsed = parse_n4_window_output(json.dumps(_payload()), window=w)
    assert parsed.can_commit_as_examined
    assert parsed.source_coverage_state == "EXAMINED_INPUT"
    assert len(parsed.proposed_findings) == 1
    candidate = parsed.proposed_findings[0]
    assert candidate["claim"]["source_quote"] == CLAUSE
    assert candidate["claim"]["review_status"] == "PROPOSED"
    assert candidate["source_refs"][0]["source_kind"] == "MODEL_SAFE_PROJECTION"
    assert candidate["source_refs"][0]["analysis_span"] == [0, len(CLAUSE)]
    assert candidate["source_refs"][0]["evidence_status"] == "EXACT_MODEL_SAFE_MATCH"


def test_invented_quote_remains_candidate_without_fabricated_source_evidence():
    result = parse_n4_window_output(
        _payload([_finding("9.6 invented penalty of 300000 EUR")]),
        window=_window(),
    )
    candidate = result.proposed_findings[0]
    assert len(result.proposed_findings) == 1
    assert candidate["source_refs"][0]["analysis_span"] is None
    assert candidate["source_refs"][0]["evidence_status"] == "NOT_FOUND_IN_MODEL_SAFE_SOURCE"
    assert candidate["claim"]["source_quote"] is None
    assert candidate["claim"]["risk_reason"]


def test_missing_quote_keeps_candidate_unverified_not_discarded():
    result = parse_n4_window_output(
        _payload([_finding(source_quote=None)]), window=_window(),
    )
    assert result.proposed_findings[0]["source_refs"][0][
        "evidence_status"
    ] == "MISSING_SOURCE_QUOTE"
    assert result.proposed_findings[0]["claim"]["source_quote"] is None


def test_repeated_quote_must_not_select_arbitrary_first_span_as_certified():
    source = CLAUSE + " // duplicated // " + CLAUSE
    parsed = parse_n4_window_output(
        _payload([_finding()]), window=_window(source),
    )
    ref = parsed.proposed_findings[0]["source_refs"][0]
    assert ref["evidence_status"] == "AMBIGUOUS_REPEATED_QUOTE"
    assert ref["analysis_span"] is None


def test_explicit_zero_candidates_only_covers_one_window_not_the_document():
    parsed = parse_n4_window_output(
        _payload(findings=[]), window=_window(),
    )
    assert parsed.proposed_findings == ()
    assert parsed.reported_examined is True
    assert parsed.source_coverage_state == "EXAMINED_INPUT"


def test_unresolved_external_reference_forces_partial_coverage_state():
    parsed = parse_n4_window_output(
        _payload(refs=["Annex 7 outside source"]), window=_window(),
    )
    assert parsed.reported_examined is True
    assert not parsed.can_commit_as_examined
    assert parsed.source_coverage_state == "PARTIAL_OR_PENDING_REFERENCES"
    assert parsed.outstanding_references == ("Annex 7 outside source",)


@pytest.mark.parametrize("payload", [
    "{",
    {"window_examined": True, "outstanding_references": []},
    {"window_examined": True, "findings": [], "outstanding_references": None},
    {"window_examined": "yes", "findings": [], "outstanding_references": []},
    {"window_examined": True, "findings": [None], "outstanding_references": []},
    _payload([{"title": "Missing reason", "category": "other"}]),
    _payload([_finding(impact={"fake": "object"})]),
])
def test_invalid_or_truncated_response_fails_explicitly(payload):
    with pytest.raises(N4WindowContractError):
        parse_n4_window_output(payload, window=_window())


def test_untrusted_source_in_prompt_is_whole_window_without_keyword_filter():
    source = ("a" * 1000) + " exception 2.5.5 " + ("b" * 700)
    windows = plan_n4_source_windows(
        source, max_context_chars=600, overlap_chars=70, revision_id="r2",
    )
    assert "".join(w.core_text for w in windows) == source
    assert all(w.context_text in n4_window_source_message(w) for w in windows)
    assert all("UNTRUSTED SOURCE WINDOW" in n4_window_source_message(w) for w in windows)
    assert any("exception 2.5.5" in w.context_text for w in windows)



def _v2_payload(*, quote, reason, examined=True, supporting=None):
    return {
        "prompt_version": "n4-compact-window-v2",
        "window_examined": examined,
        "findings": [{
            "title": "Synthetic exposure", "category": "LEGAL",
            "epc_control_id": "EPC-07",
            "risk_reason": reason, "source_quote": quote,
            "clause_ref": "9.6", "severity_proposed": "HIGH",
            "supporting_quotes": [] if supporting is None else supporting,
        }],
        "examined_clauses": [{
            "clause_ref": "9.6", "examined": True, "has_risk": True,
        }],
        "outstanding_references": [],
    }


def test_v2_multiline_quote_matches_source_whitespace_with_exact_offsets():
    source = (
        "9.6 The contractor shall pay 10 % of the price\n"
        "if the delivery milestone is late.\n"
    )
    normalized = (
        "9.6 The contractor shall pay 10 % of the price "
        "if the delivery milestone is late."
    )
    parsed = parse_n4_window_output(
        _v2_payload(
            quote=normalized,
            reason="The 10 % penalty creates a conditional exposure.",
        ),
        window=_window(source),
    )
    claim = parsed.proposed_findings[0]["claim"]
    ref = parsed.proposed_findings[0]["source_refs"][0]
    assert parsed.can_commit_as_examined
    assert parsed.examined_clauses == ("9.6",)
    assert ref["evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
    assert source[slice(*ref["analysis_span"])] == claim["source_quote"]
    assert "\n" in claim["source_quote"]
    assert not claim["quote_omits_figures"]
    assert claim["dimension"] == "LEGAL"
    assert claim["epc_control_id"] == "EPC-07"
    assert claim["severity_proposed"] == "HIGH"


def test_v2_numeric_figure_missing_in_quote_is_flagged_not_invented():
    source = (
        "9.6 The contractor shall pay damages if completion is late.\n"
        "The daily rate equals 10 % of the contract value."
    )
    parsed = parse_n4_window_output(
        _v2_payload(
            quote="The contractor shall pay damages if completion is late.",
            reason="Exposure includes 10 % of value.",
        ),
        window=_window(source),
    )
    claim = parsed.proposed_findings[0]["claim"]
    assert claim["quote_omits_figures"]
    assert claim["review_status"] == "PROPOSED"


def test_v2_requires_explicit_examination_of_all_detected_clauses():
    source = "9.6 First clause.\n10.1 Second clause."
    payload = _v2_payload(
        quote="First clause.",
        reason="A qualitative consequence may arise.",
    )
    with pytest.raises(N4WindowContractError, match="missing examined clause"):
        parse_n4_window_output(payload, window=_window(source))
    payload["examined_clauses"].append({
        "clause_ref": "10.1", "examined": True, "has_risk": False,
    })
    parsed = parse_n4_window_output(payload, window=_window(source))
    assert parsed.can_commit_as_examined


def test_v2_supporting_quotes_are_independently_anchored_and_bounded():
    source = (
        "9.6 The contractor shall pay the delay penalty.\n"
        "This does not apply to delays caused by the Employer."
    )
    payload = _v2_payload(
        quote="The contractor shall pay the delay penalty.",
        reason="The penalty has a contractual exception.",
        supporting=["This does not apply to delays caused by the Employer."],
    )
    parsed = parse_n4_window_output(payload, window=_window(source))
    candidate = parsed.proposed_findings[0]
    assert len(candidate["source_refs"]) == 2
    assert all(ref["evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
               for ref in candidate["source_refs"])
    payload["findings"][0]["supporting_quotes"] = ["a", "b", "c"]
    with pytest.raises(N4WindowContractError, match="at most 2"):
        parse_n4_window_output(payload, window=_window(source))



def test_v2_rejects_wrong_epc_dimension_and_unknown_control():
    source = "9.6 The supplier shall comply with governing law."
    payload = _v2_payload(
        quote="The supplier shall comply with governing law.",
        reason="The provision may require legal review.",
    )
    payload["findings"][0]["epc_control_id"] = "EPC-05"  # TIME, not LEGAL
    with pytest.raises(N4WindowContractError, match="EPC control and dimension"):
        parse_n4_window_output(payload, window=_window(source))
    payload["findings"][0]["epc_control_id"] = "EPC-99"
    with pytest.raises(N4WindowContractError, match="unknown EPC control"):
        parse_n4_window_output(payload, window=_window(source))
    payload["findings"][0]["epc_control_id"] = "EPC-07"
    parsed = parse_n4_window_output(payload, window=_window(source))
    assert parsed.proposed_findings[0]["claim"]["epc_control_id"] == "EPC-07"
