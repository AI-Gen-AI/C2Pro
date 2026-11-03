"""Contract traceability, deterministic and offline: the quote a reviewer sees under a finding is a span of the contract, or nothing.

Chain pinned here, link by link: the extractor's claim -> ``classify_quote`` (verbatim or withheld) -> the N4 boundary
(``risk_extractor_node`` with a fake provider) -> the persisted shape -> the reviewer read model (``_project``). The real pilot
showed why: the quote the model returned was folded into the legacy ``source`` field and never reached a reviewer, and 2 of 8
quotes of the first pilot were two sentences stitched into one. No quote is ever invented on the way.
"""

from __future__ import annotations

import pytest

from src.analysis.adapters.graph import nodes
from src.analysis.adapters.graph.nodes import _risk_contract_item, _risk_contract_payload
from src.analysis.domain.risk_provenance import (
    MIN_QUOTE_CHARS,
    NOT_CHECKED,
    NOT_FOUND,
    NOT_PROVIDED,
    VERIFIED,
    classify_quote,
)
from src.modules.hitl.application.review_findings_view import _project

CONTRACT = (
    "3.1 The Works shall commence on 01/06/2025 and shall achieve Practical Completion no later than 31/12/2025,\n"
    "in accordance with the approved programme.\n"
    "3.2 The Contractor shall achieve the structural milestone within 120 days of commencement.\n"
    "6.3 Either party may terminate for material breach not remedied within thirty (30) days of written notice."
)
Q31 = "The Works shall commence on 01/06/2025 and shall achieve Practical Completion no later than 31/12/2025, in accordance with the approved programme."
Q32 = "The Contractor shall achieve the structural milestone within 120 days of commencement."


# ── the pure rule ─────────────────────────────────────────────────────────────────────────────────────────────
def test_a_quote_found_verbatim_is_verified_even_across_a_line_break() -> None:
    assert classify_quote(Q31, CONTRACT) == (Q31, VERIFIED), "the contract wraps this sentence over two lines; whitespace must not matter"


def test_quotation_marks_around_the_quote_are_not_part_of_it() -> None:
    assert classify_quote(f"“{Q32}”", CONTRACT) == (Q32, VERIFIED)
    assert classify_quote(f'"{Q32}"', CONTRACT) == (Q32, VERIFIED)


@pytest.mark.parametrize(
    "invented",
    [
        Q31 + " " + Q32,  # two sentences stitched into one quote (what 2 of 8 quotes were in the first pilot)
        "The Contractor shall complete the Works within seven months.",  # a paraphrase
        "The Works shall commence on 01/07/2025 and shall achieve Practical Completion no later than 31/12/2025.",  # one number changed
        "the works shall commence on 01/06/2025 and shall achieve practical completion",  # case changed
    ],
)
def test_anything_that_is_not_a_contiguous_span_of_the_document_is_withheld(invented: str) -> None:
    assert classify_quote(invented, CONTRACT) == (None, NOT_FOUND)


def test_a_true_prefix_of_a_real_sentence_is_a_contiguous_span_and_is_verified() -> None:
    prefix = "Either party may terminate for material breach"
    assert classify_quote(prefix, CONTRACT) == (prefix, VERIFIED)


def test_too_short_to_prove_anything_nothing_provided_and_nothing_to_check_against() -> None:
    assert len("2.1") < MIN_QUOTE_CHARS and classify_quote("2.1", CONTRACT) == (None, NOT_FOUND)
    assert classify_quote(None, CONTRACT) == (None, NOT_PROVIDED) and classify_quote("   ", CONTRACT) == (None, NOT_PROVIDED)
    assert classify_quote(Q32, None) == (None, NOT_CHECKED) and classify_quote(Q32, "  ") == (None, NOT_CHECKED)
    assert classify_quote(123, CONTRACT) == (None, NOT_PROVIDED)


# ── the N4 boundary ───────────────────────────────────────────────────────────────────────────────────────────
def _raw(**over: object) -> dict:
    base = {
        "category": "SCHEDULE", "title": "Seven-month programme", "summary": "The programme is short", "probability": "HIGH",
        "impact": "HIGH", "clause_ref": "3.1", "source_quote": Q31, "risk_score": 9, "immediate_alert": False,
    }
    base.update(over)
    return base


def test_the_boundary_keeps_the_verified_quote_and_the_clause_reference_next_to_the_generated_description() -> None:
    payload = _risk_contract_payload(_raw(), CONTRACT)
    assert payload["source_quote"] == Q31 and payload["source_quote_status"] == VERIFIED
    assert payload["clause_ref"] == "3.1"
    assert payload["description"] == "The programme is short", "the generated text stays in its own field"
    assert payload["source_quote"] != payload["description"]


def test_the_boundary_never_stores_an_invented_quote_but_says_why() -> None:
    payload = _risk_contract_payload(_raw(source_quote=Q31 + " " + Q32), CONTRACT)
    assert payload["source_quote"] is None and payload["source_quote_status"] == NOT_FOUND
    assert payload["clause_ref"] == "3.1", "the clause label is the extractor's own and is kept either way"


def test_without_the_document_text_nothing_is_presented_as_a_citation() -> None:
    item = _risk_contract_item(_raw())
    assert item.source_quote is None and item.source_quote_status == NOT_CHECKED


def test_the_snippet_alias_is_checked_the_same_way_and_a_missing_quote_is_not_provided() -> None:
    assert _risk_contract_payload(_raw(source_quote=None, source_text_snippet=Q32), CONTRACT)["source_quote_status"] == VERIFIED
    assert _risk_contract_payload(_raw(source_quote=None), CONTRACT)["source_quote_status"] == NOT_PROVIDED


# ── through the node, with a fake provider ─────────────────────────────────────────────────────────────────────
async def test_the_risk_node_persists_quotes_only_when_they_are_in_the_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("C2PRO_AI_MOCK", "0")

    async def fake_tool(state: dict) -> dict:
        state["extracted_risks"] = [
            _raw(),  # verbatim
            _raw(title="Stitched", clause_ref="3.2", source_quote=Q31 + " " + Q32),  # invented by joining
            _raw(title="Paraphrased", clause_ref="6.3", source_quote="Termination needs thirty days of notice."),
        ]
        return state

    monkeypatch.setattr("src.core.ai.tools.get_tool", lambda *_a, **_k: fake_tool)
    state = {"document_text": CONTRACT, "node_results": [], "messages": []}
    out = await nodes.risk_extractor_node(state)  # type: ignore[arg-type]
    by_title = {r["title"]: r for r in out["extracted_risks"]}
    assert by_title["Seven-month programme"]["source_quote"] == Q31
    assert by_title["Stitched"]["source_quote"] is None and by_title["Stitched"]["source_quote_status"] == NOT_FOUND
    assert by_title["Paraphrased"]["source_quote"] is None and by_title["Paraphrased"]["source_quote_status"] == NOT_FOUND
    assert {r["clause_ref"] for r in out["extracted_risks"]} == {"3.1", "3.2", "6.3"}
    for risk in out["extracted_risks"]:  # whatever was stored as a quote IS in the contract
        assert risk["source_quote"] is None or " ".join(risk["source_quote"].split()) in " ".join(CONTRACT.split())


# ── the reviewer read model ───────────────────────────────────────────────────────────────────────────────────
def test_the_reviewer_read_model_exposes_the_reference_the_quote_and_its_status_next_to_the_description() -> None:
    stored = _risk_contract_payload(_raw(), CONTRACT)
    shown = _project(stored)
    assert shown["clause_ref"] == "3.1" and shown["source_quote"] == Q31 and shown["source_quote_status"] == VERIFIED
    assert shown["description"] == "The programme is short"
    withheld = _project(_risk_contract_payload(_raw(source_quote="made up text that is not in the contract at all"), CONTRACT))
    assert withheld.get("source_quote") is None
    assert withheld["source_quote_status"] == NOT_FOUND
