"""A7 focal occurrence contract; no provider, database, or physical-PDF claim."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from src.analysis.adapters.graph import n4_governed_bridge as bridge
from src.analysis.domain import n4_compact_window_response as parser
from src.analysis.domain.n4_consolidation import consolidate_candidates
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.documents.domain.quote_page_locator import PageSpan

REVISION = "00000000-0000-0000-0000-000000000001"
QUOTES = (
    "The contractor shall pay the delay penalty.",
    "This does not apply to delays caused by the Employer.",
    "Notice must be given in writing.",
)
SOURCE = "9.6 " + "\n".join(QUOTES)
CASES = (
    ("primary_only", QUOTES[0], (), (1,)),
    ("two_exact", QUOTES[0], QUOTES[1:2], (1, 2)),
    ("three_exact", QUOTES[0], QUOTES[1:], (1, 2, 3)),
    ("invalid_support", QUOTES[0], ("Invented supporting text.",), (1, None)),
    ("missing_primary", None, QUOTES[1:2], (None, 2)),
    ("invalid_primary", "Invented primary text.", QUOTES[1:2], (None, 2)),
)


def _fixture(primary, supporting):
    """Exact positional A5 output shape, usable before A5 incorporation."""
    literals = []
    refs = []
    for value in (primary, *supporting):
        start = SOURCE.find(value) if value is not None else -1
        literal = value if start >= 0 else None
        status = (
            "EXACT_MODEL_SAFE_MATCH" if literal else
            "MISSING_SOURCE_QUOTE" if value is None else "NOT_FOUND_IN_MODEL_SAFE_SOURCE"
        )
        ref = {
            "source_kind": "MODEL_SAFE_PROJECTION",
            "source_sha256": sha256(SOURCE.encode()).hexdigest(),
            "document_revision_id": REVISION,
            "evidence_status": status,
            "analysis_span": [start, start + len(value)] if literal else None,
        }
        if not literal:
            ref["quote_sha256"] = sha256((value or "").encode()).hexdigest()
            if not refs:
                ref["reported_clause_ref"] = "9.6"
        refs.append(ref)
        literals.append(literal)
    return {
        "finding_key": "a" * 64,
        "claim": {
            "title": "Delay liability", "category": "LEGAL",
            "risk_reason": "Review the delay liability and its exceptions.",
            "clause_ref": "9.6", "source_quote": literals[0],
            "source_evidence_status": refs[0]["evidence_status"],
            "supporting_quotes": literals[1:],
        },
        "source_refs": refs,
    }


def _real_parser(primary, supporting):
    window = plan_n4_source_windows(
        SOURCE, revision_id=REVISION, max_context_chars=1200, overlap_chars=80,
    )[0]
    output = parser.parse_n4_window_output({
        "prompt_version": "n4-compact-window-v2",
        "window_examined": True,
        "findings": [{
            "title": "Delay liability", "category": "LEGAL",
            "epc_control_id": "EPC-07", "severity_proposed": "HIGH",
            "risk_reason": "Review the delay liability and its exceptions.",
            "clause_ref": "9.6", "source_quote": primary,
            "supporting_quotes": list(supporting),
        }],
        "examined_clauses": [{"clause_ref": "9.6", "examined": True, "has_risk": True}],
        "outstanding_references": [],
    }, window=window)
    assert output.reported_examined
    assert len(output.proposed_findings) == 1
    candidate = output.proposed_findings[0]
    assert len(candidate["source_refs"]) == 1 + len(supporting)
    assert "decisive_evidence" not in candidate["claim"]
    return candidate


def _pages():
    result = []
    offset = 0
    for number, line in enumerate(SOURCE.splitlines(), start=1):
        result.append(PageSpan(number, offset, offset + len(line)))
        offset += len(line) + 1
    return result


def _verify(candidate, expected):
    original = deepcopy(candidate)
    result = bridge._candidate_payload(
        candidate["claim"], candidate["source_refs"], SOURCE,
        revision_id=REVISION, page_spans=_pages(), map_claimed=True,
    )
    evidence = result["occurrence_evidence"]
    assert candidate == original
    assert len(evidence) == len(expected)
    assert [o["ref_index"] for o in evidence] == list(range(len(expected)))
    assert [o["role"] for o in evidence] == ["primary"] + ["supporting"] * (len(expected) - 1)
    assert [o["original_ref"] for o in evidence] == candidate["source_refs"]
    assert [o["page_number"] for o in evidence] == list(expected)
    assert result["page_number"] == expected[0]
    assert result["source_quote"] == (QUOTES[0] if expected[0] else None)
    for occurrence, page, ref in zip(evidence, expected, candidate["source_refs"], strict=True):
        if page is None:
            assert occurrence["source_quote"] is None
            assert occurrence["page_verification_status"] == "PAGE_UNRESOLVED"
            assert "located_span" not in occurrence
        else:
            assert occurrence["source_quote"] == QUOTES[page - 1]
            assert occurrence["page_verification_status"] == "PAGE_LOCATED"
            assert occurrence["located_span"] == ref["analysis_span"]
            assert occurrence["page_start"] == occurrence["page_end"] == page
    return result


@pytest.mark.parametrize(("name", "primary", "supporting", "expected"), CASES,
                         ids=[case[0] for case in CASES])
def test_a7_positional_occurrences(name, primary, supporting, expected):
    _verify(_fixture(primary, supporting), expected)


@pytest.mark.skipif(
    getattr(parser, "N4_WINDOW_PROMPT_VERSION", None) != "n4-compact-window-v2",
    reason="requires the separately governed A5 v2 candidate",
)
@pytest.mark.parametrize(("name", "primary", "supporting", "expected"), CASES,
                         ids=[case[0] for case in CASES])
def test_a7_authentic_a5_occurrences(name, primary, supporting, expected):
    _verify(_real_parser(primary, supporting), expected)


def test_a7_preserves_member_associations_after_consolidation():
    first = _fixture(QUOTES[0], QUOTES[1:2])
    second = _fixture(QUOTES[0], QUOTES[2:])
    second["finding_key"] = "b" * 64
    items = []
    for ordinal, candidate in enumerate((first, second)):
        result = _verify(candidate, (1, ordinal + 2))
        items.append({
            **result, "run_id": "run", "finding_key": candidate["finding_key"],
            "window_ordinal": ordinal, "source_refs": candidate["source_refs"],
        })
    merged = consolidate_candidates(items)
    assert len(merged) == 1
    members = merged[0]["occurrence_members"]
    assert [m["finding_key"] for m in members] == ["a" * 64, "b" * 64]
    assert [m["window_ordinal"] for m in members] == [0, 1]
    assert [m["occurrences"][1]["page_number"] for m in members] == [2, 3]
    assert len(merged[0]["source_refs"]) == 4


@pytest.mark.parametrize("corruption", ["cardinality", "foreign_hash", "foreign_revision"])
def test_a7_corrupt_binding_is_not_promoted(corruption):
    candidate = _fixture(QUOTES[0], QUOTES[1:2])
    if corruption == "cardinality":
        candidate["claim"]["supporting_quotes"] = []
    elif corruption == "foreign_hash":
        candidate["source_refs"][1]["source_sha256"] = "f" * 64
    else:
        candidate["source_refs"][1]["document_revision_id"] = "other"
    result = bridge._candidate_payload(
        candidate["claim"], candidate["source_refs"], SOURCE,
        revision_id=REVISION, page_spans=_pages(), map_claimed=True,
    )
    assert result["source_quote"] is None
    assert result["page_number"] is None
    assert all(o["source_quote"] is None for o in result["occurrence_evidence"])
