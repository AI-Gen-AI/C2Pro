"""Policy regression: no lexical contract logic may decide N3/N12 semantics.

This tests failures/unknowns with fake AI, not semantic gold matching.
"""
from __future__ import annotations

import pytest

from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand,
    CritiqueExtractionUseCase,
)
from src.analysis.domain.ai_extraction import (
    DocumentTypeClassificationService,
    _fallback_doc_type,
)


class FakeAI:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def run_extraction(self, system_prompt, user_content):
        self.calls.append((system_prompt, user_content))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize(
    "source",
    [
        "Contract for software cost center; the project also contains a schedule.",
        "Presupuesto y cláusulas sobre ingeniería con cronograma y facturas.",
        "A new category of professional services engagement not in a fixed keyword list.",
    ],
)
def test_n3_unknown_is_not_guessed_by_keywords(source):
    assert _fallback_doc_type(source) == "classification_unassessed"


@pytest.mark.asyncio
async def test_n3_model_error_is_fail_closed_not_keyword_contract():
    ai = FakeAI(error=RuntimeError("transient provider failure"))
    result = await DocumentTypeClassificationService().classify(
        text="A construction budget with an annex called Contract and a project schedule.",
        ai=ai,
    )
    assert result == "classification_unassessed"
    assert len(ai.calls) == 1


@pytest.mark.asyncio
async def test_n12_does_not_assert_specific_cure_period_from_regex():
    source = (
        "5.2 Defective work identified during inspection shall be rectified "
        "at the Contractor's cost within fourteen (14) days of written notice."
    )
    ai = FakeAI(response={"status": "OK", "notes": "", "findings": []})
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{
                "title": "Defect rectification with unclear period",
                "description": "No agreed timeframe for defect rectification is provided.",
                "clause_ref": "5.2", "confidence": 0.95,
            }],
            extracted_wbs=[], doc_type="contract", retry_count=0,
            source_text=source, source_complete=True,
        )
    )
    # N12 may not turn keyword matches into verified contractual judgments.
    assert result.status == "OK"
    assert result.retry_count == 0
    assert result.human_approval_required is True
    assert "source specifies a deadline" not in result.critique_notes


@pytest.mark.asyncio
async def test_n12_any_domain_may_return_source_bound_model_concern_without_rule():
    source = (
        "Service provider shall furnish reports for each site in three languages "
        "within eleven business days, except when data is withheld by the customer."
    )
    ai = FakeAI(response={
        "status": "RETRY",
        "notes": "Source-specific exception may alter responsibility.",
        "findings": [{
            "clause_ref": None,
            "issue_type": "missing_condition",
            "source_quote": source,
            "explanation": "The customer data exception may affect timing.",
        }],
    })
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"title": "Deliverables", "confidence": 0.91}],
            extracted_wbs=[], doc_type="contract", retry_count=0,
            source_text=source, source_complete=True,
        )
    )
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required
    assert result.retry_count == 0
    assert len(ai.calls) == 1


@pytest.mark.asyncio
async def test_n3_unknown_routes_to_terminal_without_running_n4(monkeypatch):
    from src.analysis.adapters.graph import nodes
    from src.analysis.adapters.graph.workflow import (
        unclassified_document_node,
    )

    unknown = FakeAI(response={"doc_type": "an unrecognized document family"})
    monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: unknown)
    state = {
        "document_text": (
            "This business project file uses the terms contract, budget and schedule, "
            "but its actual document family cannot be determined from a filename."
        ),
        "messages": [],
        "node_results": [],
        "tenant_id": None,
    }

    classified = await nodes.router_node(state)
    assert classified["doc_type"] == "classification_unassessed"
    assert classified["node_results"][-1].degradation_reason == "classification_unassessed"
    assert len(unknown.calls) == 1

    terminal = unclassified_document_node(classified)
    assert terminal["workflow_terminated"] is True
    assert terminal["termination_reason"] == "classification_unassessed"
    assert terminal["extracted_risks"] == []
    assert terminal["extracted_wbs"] == []
    assert terminal["confidence_score"] is None
    assert terminal["human_approval_required"] is False


def test_n4_keeps_non_epc_contract_text_without_keyword_filter():
    from src.analysis.adapters.ai.tools.risk_extraction_tool import (
        RiskExtractionTool,
    )

    source = (
        "Provision of multilingual field services; the provider may decline "
        "delivery when customer data is unavailable. The project also contains "
        "a statement that does not match any predetermined EPC dictionary."
    )
    prepared = RiskExtractionTool().extract_input_from_state({
        "anonymized_text": source,
        "document_text": "Original PII must not be sent",
    })
    assert source in prepared.document_text
    assert "Original PII must not be sent" not in prepared.document_text
    assert prepared.strict_completeness is True


@pytest.mark.asyncio
async def test_n12_other_document_type_risks_are_never_approved_automatically(monkeypatch):
    """The N3 'other' route enters N4: all proposed risks need HITL."""
    ai = FakeAI(response={"status": "OK", "notes": "", "findings": []})
    source = (
        "Software operations: The supplier shall deliver the daily incident "
        "report to the client in the agreed portal by 08:00 on workdays."
    )
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{
                "title": "Unusual reporting duty",
                "description": "The exact daily reporting condition may create an exposure.",
                "confidence": 0.99,
            }],
            extracted_wbs=[],
            doc_type="other",
            retry_count=0,
            source_text=source,
            source_complete=True,
        )
    )
    assert result.status == "OK"
    assert result.confidence == 0.99
    assert result.human_approval_required is True
    assert result.retry_count == 0

    from src.analysis.adapters.graph.workflow import _next_after_critique_v2

    monkeypatch.setenv("C2PRO_SKIP_HITL", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert _next_after_critique_v2({
        "human_approval_required": result.human_approval_required,
        "critique_notes": result.critique_notes,
        "retry_count": result.retry_count,
        "doc_type": "other",
    }) == "human_interrupt"
