"""WBS 1.3: contract-risk evidence is checked before HITL, not after approval.

This is evidence matching against the model-safe text, NOT certification of
a PDF file or independent verification of a model's legal interpretation.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.analysis.adapters.graph import nodes

SOURCE = (
    "3.1 The Contractor shall achieve Mechanical Completion by 2027-09-30, "
    "and provide acceptance evidence before handover."
)
QUOTE = "The Contractor shall achieve Mechanical Completion by 2027-09-30"


def _state(risks=None, *, doc_type="contract"):
    return {
        "document_text": SOURCE, "anonymized_text": SOURCE,
        "doc_type": doc_type, "extracted_risks": risks if risks is not None else [],
        "extracted_wbs": [], "citations": [], "citation_validation_passed": False,
        "messages": [], "node_results": [], "retry_count": 0,
        "tenant_id": None, "document_revision_id": None,
        "human_approval_required": False, "confidence_score": None,
        "critique_notes": "", "human_feedback": "",
    }


def _risk(quote=QUOTE, title="Handover delay"):
    return {
        "title": title, "clause_ref": "3.1", "source_quote": quote,
        "source_quote_status": "VERIFIED" if quote == QUOTE else "NOT_FOUND_IN_DOCUMENT",
    }


def test_good_contract_quote_is_stamped_before_hitl():
    state = _state([_risk()])
    nodes._stamp_pre_hitl_contract_risk_evidence(state)
    assert state["risk_pre_hitl_evidence_passed"] is True
    assert state["citation_validation_passed"] is True
    assert state["citations"] == [{
        "type": "risk", "item": "Handover delay", "quote": QUOTE,
        "found_in_source": True,
    }]
    summary = nodes._contract_risk_review_summary(state)
    assert summary["risk_source_evidence_verified"] == 1
    assert summary["risk_source_evidence_total"] == 1
    assert summary["risk_source_evidence"][0]["found_in_analysis_text"] is True
    assert summary["risk_source_evidence"][0]["source_quote"] == QUOTE


def test_stitched_or_unverified_quote_is_not_presented_as_proof():
    state = _state([
        _risk(),
        _risk(QUOTE + " The Contractor shall pay an invented penalty.", "Invented"),
    ])
    nodes._stamp_pre_hitl_contract_risk_evidence(state)
    summary = nodes._contract_risk_review_summary(state)
    assert summary["risk_source_evidence_verified"] == 1
    assert summary["risk_source_evidence_total"] == 2
    assert summary["risk_source_evidence_passed"] is False
    assert summary["risk_source_evidence"][1]["source_quote"] is None
    assert summary["risk_source_evidence"][1]["found_in_analysis_text"] is False
    assert state["citation_validation_passed"] is False


def test_empty_risks_and_missing_source_are_unassessed_not_passed():
    state = _state([])
    nodes._stamp_pre_hitl_contract_risk_evidence(state)
    assert state["risk_pre_hitl_evidence_passed"] is False
    assert state["citation_validation_passed"] is False
    assert nodes._contract_risk_review_summary(state)["risk_source_evidence_total"] == 0
    state = _state([_risk()])
    state["anonymized_text"] = "Redacted content instead of quote"
    nodes._stamp_pre_hitl_contract_risk_evidence(state)
    assert nodes._contract_risk_review_summary(state)["risk_source_evidence_verified"] == 0


def test_noncontract_and_technical_spec_remain_unchanged():
    state = _state([_risk()], doc_type="technical_spec")
    nodes._stamp_pre_hitl_contract_risk_evidence(state)
    assert state["citations"] == []
    assert nodes._contract_risk_review_summary(state) == {}


@pytest.mark.asyncio
async def test_critique_cannot_waive_contract_evidence_gate(monkeypatch):
    class FakeCritique:
        def __init__(self, **kwargs): pass

        async def execute(self, cmd):
            return SimpleNamespace(
                confidence=0.99, retry_count=0, critique_notes="",
                human_approval_required=False, status="OK",
            )

    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "get_ai_service", lambda _tenant: object())
    monkeypatch.setattr(nodes, "CritiqueExtractionUseCase", FakeCritique)

    state = _state([_risk("Invented quote not present in the original document")])
    out = await nodes.critique_node(state)
    assert out["citation_validation_passed"] is False
    assert out["human_approval_required"] is True
    assert out["confidence_score"] is None
    assert out["retry_count"] == 0
    assert nodes._contract_risk_review_summary(out)["risk_source_evidence_verified"] == 0


def test_other_type_risks_get_the_same_literal_quote_provenance_check():
    """N3 routes 'other' to N4; its source evidence must not be skipped."""
    state = _state([_risk()], doc_type="other")
    nodes._stamp_pre_hitl_contract_risk_evidence(state)
    assert state["risk_pre_hitl_evidence_passed"] is True
    assert state["citation_validation_passed"] is True
    summary = nodes._contract_risk_review_summary(state)
    assert summary["risk_source_evidence_total"] == 1
    assert summary["risk_source_evidence_verified"] == 1
    assert summary["risk_source_evidence"][0]["source_quote"] == QUOTE


@pytest.mark.asyncio
async def test_other_type_invented_quote_never_passes_pre_hitl_gate(monkeypatch):
    class FakeCritique:
        def __init__(self, **kwargs): pass

        async def execute(self, cmd):
            return SimpleNamespace(
                confidence=0.99, retry_count=0, critique_notes="",
                human_approval_required=False, status="OK",
            )

    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "get_ai_service", lambda _tenant: object())
    monkeypatch.setattr(nodes, "CritiqueExtractionUseCase", FakeCritique)

    state = _state([_risk("Invented SLA obligation not in the source.")], doc_type="other")
    out = await nodes.critique_node(state)
    assert out["risk_pre_hitl_evidence_passed"] is False
    assert out["citation_validation_passed"] is False
    assert out["human_approval_required"] is True
    assert out["confidence_score"] is None
    summary = nodes._contract_risk_review_summary(out)
    assert summary["risk_source_evidence_total"] == 1
    assert summary["risk_source_evidence_verified"] == 0
    assert summary["risk_source_evidence"][0]["source_quote"] is None
