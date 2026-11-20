"""VS-2 experimental contract tests. No LLM/provider/DB/network calls."""
from __future__ import annotations

import json

import pytest

from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.analysis.domain.n4_typed_evidence_v2 import (
    N4_TYPED_EVIDENCE_V2_SYSTEM_PROMPT,
    N4V2ContractError,
    parse_n4_typed_evidence_v2,
)

SOURCE = (
    "2.5.5 The Contractor shall pay $5,000 per Day for delayed Mechanical Completion.\n"
    "The Contractor shall pay $10,000 per Day for delayed Substantial Completion.\n"
    "The Contractor shall pay $20,000 per Day for delayed Final Completion.\n"
    "Liquidated damages shall not exceed [5] percent of the Contract Price.\n"
    "This provision does not apply to delays caused by the Owner or Utility.\n"
    "9.6 The termination fee shall be ten percent (5%) of the Contract Price.\n"
    "Demobilization costs shall not exceed 2% of the Contract Price.\n"
    "3.2.1 Milestone payments shall be as specified in Table D-2 of Exhibit D.\n"
)


def _window(source=SOURCE):
    return plan_n4_source_windows(
        source, revision_id="vs2-immutable-rev",
        max_context_chars=2800, overlap_chars=100,
    )[0]


def _quote(text, role="basis"):
    return {"role": role, "quote": text}


def _fact(local_id="F1", **kw):
    return {
        "record_type": "fact", "local_id": local_id, "kind": "penalty",
        "title": "Daily delay penalties", "clause_ref": "2.5.5",
        "value_text": "$5,000",
        "evidence": [
            _quote(
                "The Contractor shall pay $5,000 per Day for delayed Mechanical Completion.",
                "amount",
            ),
            _quote(
                "Liquidated damages shall not exceed [5] percent of the Contract Price.",
                "cap",
            ),
            _quote(
                "This provision does not apply to delays caused by the Owner or Utility.",
                "exception",
            ),
        ],
        **kw,
    }


def _risk(**kw):
    return {
        "record_type": "risk", "local_id": "R1",
        "category": "schedule",
        "title": "Conditional delay exposure",
        "clause_ref": "2.5.5",
        "risk_reason": "Delay can create penalty exposure only when contractual conditions apply.",
        "linked_fact_ids": ["F1"],
        "evidence": [
            _quote(
                "The Contractor shall pay $10,000 per Day for delayed Substantial Completion.",
                "amount",
            ),
            _quote(
                "The Contractor shall pay $20,000 per Day for delayed Final Completion.",
                "amount",
            ),
        ],
        **kw,
    }


def _payload(*records, refs=None, examined=True):
    return {
        "window_examined": examined,
        "records": list(records),
        "outstanding_references": [] if refs is None else refs,
    }


def test_fact_and_risk_are_typed_without_promoting_fact_to_risk_or_score():
    w = _window()
    out = parse_n4_typed_evidence_v2(_payload(_fact(), _risk()), window=w)
    assert out.can_commit_as_examined
    assert len(out.facts) == 1 and len(out.risks) == 1
    f = out.facts[0]["claim"]
    r = out.risks[0]["claim"]
    assert f["kind"] == "penalty"
    assert f["value_text"] == "$5,000"
    assert f["value_status"] == "N2_QUOTE_CONTAINS_REPORTED_VALUE"
    assert r["linked_fact_ids"] == ["F1"]
    assert r["risk_reason"] and r["severity"] is None
    assert all(not v["claim"]["alerts_allowed"] and
               not v["claim"]["score_allowed"] and
               not v["claim"]["approvable"]
               for v in [out.facts[0], out.risks[0]])


def test_independently_verified_amount_cap_and_exception_have_separate_offsets():
    w = _window()
    out = parse_n4_typed_evidence_v2(_payload(_fact()), window=w)
    f = out.facts[0]
    spans = [ref["analysis_span"] for ref in f["source_refs"]]
    assert len(spans) == 3
    assert len({tuple(s) for s in spans}) == 3
    assert [e["role"] for e in f["claim"]["decisive_evidence"]] == [
        "amount", "cap", "exception",
    ]
    assert all(ref["evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
               for ref in f["source_refs"])
    assert all(ref["source_sha256"] == w.source_sha256 and
               ref["document_revision_id"] == w.revision_id
               for ref in f["source_refs"])
    assert all(ref["original_pdf_status"] == "UNVERIFIED"
               for ref in f["source_refs"])
    for ref, item in zip(f["source_refs"], f["claim"]["decisive_evidence"], strict=True):
        start, end = ref["analysis_span"]
        assert SOURCE[start:end] == item["quote"]


def test_termination_word_figure_conflict_does_not_select_a_percentage():
    fact = {
        "record_type": "fact", "local_id": "F6", "kind": "termination",
        "title": "Conflicting termination fee", "clause_ref": "9.6",
        "value_text": None,
        "evidence": [
            _quote(
                "The termination fee shall be ten percent (5%) of the Contract Price.",
                "contradiction",
            ),
            _quote(
                "Demobilization costs shall not exceed 2% of the Contract Price.",
                "cap",
            ),
        ],
    }
    out = parse_n4_typed_evidence_v2(_payload(fact), window=_window())
    claim = out.facts[0]["claim"]
    assert claim["value_text"] is None
    assert claim["value_status"] == "NO_VALUE"
    assert len(claim["decisive_evidence"]) == 2
    assert all(x["quote"] for x in claim["decisive_evidence"])


def test_missing_exhibit_is_not_treated_as_verified_schedule():
    missing_annex = {
        "record_type": "fact", "local_id": "FD", "kind": "payment",
        "title": "Milestone payment schedule is externally referenced",
        "clause_ref": "3.2.1", "value_text": None,
        "evidence": [_quote(
            "Milestone payments shall be as specified in Table D-2 of Exhibit D.",
            "cross_reference",
        )],
    }
    out = parse_n4_typed_evidence_v2(
        _payload(missing_annex, refs=["Missing Exhibit D Table D-2"]),
        window=_window(),
    )
    assert len(out.facts) == 1 and not out.risks
    assert not out.can_commit_as_examined
    assert out.source_coverage_state == "PARTIAL_OR_PENDING_REFERENCES"
    assert out.outstanding_references == ("Missing Exhibit D Table D-2",)


def test_unlocated_and_repeated_quotes_are_not_disclosed_as_verified_evidence():
    bad = _fact(evidence=[
        _quote("The contract imposes a totally invented $300,000 fine.", "amount"),
        _quote("The Contractor shall pay $5,000 per Day for delayed Mechanical Completion.", "amount"),
    ])
    repeated_source = SOURCE + "\n" + SOURCE
    out = parse_n4_typed_evidence_v2(_payload(bad), window=_window(repeated_source))
    evidence = out.facts[0]["claim"]["decisive_evidence"]
    assert [e["evidence_status"] for e in evidence] == [
        "NOT_FOUND_IN_MODEL_SAFE_SOURCE", "AMBIGUOUS_REPEATED_QUOTE",
    ]
    assert all(e["quote"] is None for e in evidence)
    assert all(ref["analysis_span"] is None for ref in out.facts[0]["source_refs"])
    assert out.facts[0]["claim"]["value_status"] == "VALUE_NOT_CITED"
    assert out.facts[0]["claim"]["value_text"] is None


def test_value_not_in_any_verified_quote_is_withheld_as_unverified():
    f = _fact(value_text="$99,999")
    out = parse_n4_typed_evidence_v2(_payload(f), window=_window())
    assert out.facts[0]["claim"]["value_text"] is None
    assert out.facts[0]["claim"]["value_status"] == "VALUE_NOT_CITED"


@pytest.mark.parametrize("invalid", [
    {"record_type": "risk", "title": "Missing local ID",
     "category": "other", "risk_reason": "This is a substantial risk.",
     "evidence": [_quote("The Contractor shall pay $5,000 per Day for delayed Mechanical Completion.")]},
    _fact(local_id="R1"),
    _risk(linked_fact_ids=["F404"]),
    _risk(linked_fact_ids=["F1", "F1"]),
    _fact(evidence=[{"role": "amount", "quote": "2%"}]),
    _fact(evidence=[{"role": "not_a_real_evidence_role", "quote": SOURCE[:70]}]),
    _fact(evidence=[]),
    _fact(kind="invented"),
    _fact(value_text={"euro": 50}),
])
def test_malformed_or_unlinked_typed_records_fail_explicitly(invalid):
    with pytest.raises(N4V2ContractError):
        parse_n4_typed_evidence_v2(_payload(_fact(), invalid), window=_window())


def test_duplicate_local_ids_fail_without_overwriting_prior_facts():
    with pytest.raises(N4V2ContractError, match="Duplicate"):
        parse_n4_typed_evidence_v2(_payload(_fact(), _fact()), window=_window())


def test_invalid_truncated_json_never_means_empty_extracted_records():
    with pytest.raises(N4V2ContractError):
        parse_n4_typed_evidence_v2('{"window_examined":true,"records":[', window=_window())


def test_blank_unresolved_reference_fails():
    with pytest.raises(N4V2ContractError):
        parse_n4_typed_evidence_v2(_payload(refs=[""]), window=_window())


def test_window_not_examined_does_not_claim_coverage_even_with_facts():
    out = parse_n4_typed_evidence_v2(
        _payload(_fact(), examined=False),
        window=_window(),
    )
    assert len(out.facts) == 1
    assert not out.can_commit_as_examined
    assert out.source_coverage_state == "PARTIAL_OR_PENDING_REFERENCES"


def test_json_string_and_dict_are_equivalent_and_source_digest_is_stable():
    payload = _payload(_fact(), _risk())
    w = _window()
    a = parse_n4_typed_evidence_v2(payload, window=w)
    b = parse_n4_typed_evidence_v2(json.dumps(payload), window=w)
    assert a == b
    assert a.facts[0]["finding_key"] == b.facts[0]["finding_key"]


def test_no_arbitrary_top_n_or_hidden_provider_and_original_pdf_certification():
    prompt = N4_TYPED_EVIDENCE_V2_SYSTEM_PROMPT.casefold()
    for term in (
        "entire", "contract", "evidence", "exception", "cap",
        "confidentiality", "insurance", "payments", "cross-references",
        "no", "untrusted data", "only one compact json",
    ):
        assert term in prompt
    assert "do not call tools" in prompt
    assert "never discard material facts to reach a top-n" in prompt
    out = parse_n4_typed_evidence_v2(
        _payload(*[
            _fact(local_id=f"F{x}", title=f"Material obligation {x}")
            for x in range(1, 31)
        ]),
        window=_window(),
    )
    assert len(out.facts) == 30
    assert not out.risks
