"""P0 CORE: original structured source rows flow to action/report assembly.

These checks are pure, use no provider, and never treat observed source data
as an approved project budget or schedule baseline.
"""

from __future__ import annotations

from decimal import Decimal

from src.analysis.application.project_source_evidence import summarize_source_units
from src.analysis.domain.report_assembly import (
    DecisionPackageAssemblyService,
    DecisionPackageInput,
    ReportAssemblyService,
    ReportInput,
)


def _source_row(family: str, locator: str, payload: dict):
    return {
        "document_id": "00000000-0000-0000-0000-000000000001",
        "revision_id": "00000000-0000-0000-0000-000000000002",
        "source_locator": locator,
        "unit_sha256": "aa" * 32,
        "family": family,
        "payload": payload,
    }


def _decision(**updates) -> DecisionPackageInput:
    data = dict(
        coherence_score=None, coherence_score_version=None,
        extracted_risks=[], extracted_stakeholders=[], extracted_wbs=[],
        bom_items=[], citations=[], citation_validation_passed=False,
        human_feedback="",
    )
    data.update(updates)
    return DecisionPackageInput(**data)


def test_summary_keeps_source_origin_and_does_not_approve_budget_or_schedule():
    budget = [_source_row("budget", "Budget!4", {
        "kind": "line_item", "quantity": "3.500",
        "unit_price": "12.750", "currency": "EUR",
    })]
    schedule = [_source_row("schedule", "Plan!8", {
        "kind": "activity", "start_date": "2027-01-06",
        "predecessors": "SCH-01 FS+2d",
    })]
    summary = summarize_source_units(budget, schedule)
    assert summary["state"] == "SOURCE_OBSERVED_NOT_APPROVED"
    assert summary["baseline_approved"] is False
    assert summary["budget"]["observed_rows"] == 1
    assert summary["budget"]["preview_rows"][0]["fields"]["quantity"] == "3.500"
    assert summary["budget"]["preview_rows"][0]["source_locator"] == "Budget!4"
    assert summary["schedule"]["preview_rows"][0]["fields"]["predecessors"] == "SCH-01 FS+2d"
    assert summary["schedule"]["coverage"] == "NOT_ASSESSED"
    assert summary["schedule"]["baseline_approved"] is False


def test_no_source_rows_not_reported_as_zero_budget():
    result = summarize_source_units([], [])
    assert result["state"] == "NO_CANONICAL_SOURCE_ROWS"
    assert result["budget"]["state"] == "NO_CANONICAL_SOURCE_ROWS"
    assert result["schedule"]["state"] == "NO_CANONICAL_SOURCE_ROWS"
    assert result["budget"]["coverage"] == "NOT_ASSESSED"


def test_source_preview_cap_never_claims_exhaustive_coverage():
    rows = [_source_row("budget", f"Budget!{n}", {"kind": "line_item", "price": str(n)}) for n in range(10)]
    result = summarize_source_units(rows, [], max_preview_per_family=3)
    assert result["budget"]["observed_rows"] == 10
    assert len(result["budget"]["preview_rows"]) == 3
    assert result["budget"]["truncated"] is True
    assert result["budget"]["coverage"] == "NOT_ASSESSED"


def test_n11_creates_real_proposals_from_mitigations_without_inventing_owners():
    risk = {
        "title": "Delay penalties",
        "impact": "HIGH",
        "mitigation_suggestion": "Review milestone recovery measures with EPC planner.",
        "clause_ref": "EPC-03",
        "source_quote": "Contractor shall pay liquidated damages for completion delays.",
    }
    source = summarize_source_units(
        [_source_row("budget", "Budget!6", {"kind": "line_item", "quantity": "5"})], []
    )
    decision = DecisionPackageAssemblyService().assemble(
        _decision(extracted_risks=[risk], project_source_evidence=source)
    )
    assert len(decision["proposed_actions"]) == 1
    action = decision["proposed_actions"][0]
    assert action["proposed_action"] == risk["mitigation_suggestion"]
    assert action["priority_proposal"] == "P2"
    assert action["priority_basis"] == "model_extracted_risk_impact"
    assert action["owner"] is None and action["due_date"] is None
    assert action["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"
    assert action["source_evidence"]["clause_ref"] == "EPC-03"
    assert action["source_evidence"]["verification"] == "REQUIRES_SOURCE_VALIDATION"
    assert decision["evidence_links"] == []
    assert decision["project_source_evidence"] == source


def test_n11_does_not_fabricate_action_without_mitigation():
    decision = DecisionPackageAssemblyService().assemble(
        _decision(extracted_risks=[{"title": "Risk without action", "impact": "CRITICAL"}])
    )
    assert decision["proposed_actions"] == []


def test_n16_internal_report_exposes_observations_and_decisions():
    observed = summarize_source_units([], [_source_row("schedule", "Plan!9", {
        "kind": "activity", "end_date": "2027-04-12",
    })])
    decision = DecisionPackageAssemblyService().assemble(_decision(
        project_source_evidence=observed
    ))
    report = ReportAssemblyService().assemble(ReportInput(
        project_id="p", document_id="d", doc_type="contract",
        document_category="LEGAL", analysis_id=None,
        extracted_risks=[], extracted_wbs=[], extracted_stakeholders=[],
        bom_items=[], coherence_score=None, coherence_score_version=None,
        confidence_score=None, citation_validation_passed=False,
        pii_redactions=[], raci_matrix=[], coherence_breakdown={},
        citations=[], knowledge_graph_nodes=[], knowledge_graph_edges=[],
        decision_package=decision, human_approval_required=True,
        human_feedback="", project_source_evidence=observed,
    ))
    assert report["project_source_evidence"]["schedule"]["observed_rows"] == 1
    assert report["decision_package"]["proposed_actions"] == []
    assert report["summary"]["coherence_score"] is None
