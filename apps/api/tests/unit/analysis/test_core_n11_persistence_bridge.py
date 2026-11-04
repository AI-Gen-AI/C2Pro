"""Focused CORE pilot contract: N11 proposal persistence (no approvals invented)."""

from src.analysis.application.trusted_materialization import MaterializationContent
from src.analysis.adapters.graph.document_artifact_builder import build_document_artifact
from src.analysis.adapters.graph.nodes import _risk_contract_payload
from src.analysis.adapters.graph.workflow import build_workflow
from src.analysis.adapters.graph.nodes_extended import decision_intelligence_node
import asyncio
from src.analysis.domain.report_assembly import decision_snapshot_for_persistence


def _proposal():
    return {
        "title": "Late mechanical handover",
        "proposed_action": "Reconcile milestone with contract",
        "priority_proposal": "P2",
        "priority_basis": "model_extracted_risk_impact",
        "risk_impact": "HIGH",
        "status": "PROPOSED_REQUIRES_HUMAN_REVIEW",
        "owner": "invented-owner",
        "due_date": "2030-01-01",
        "source_evidence": {
            "document_id": "doc-A",
            "clause_ref": "8.2",
            "source_quote": "Must complete in June",
            "verification": "FOUND",
        },
    }


def test_n11_snapshot_pins_revision_and_does_not_promote_review():
    snapshot = decision_snapshot_for_persistence(
        {"proposed_actions": [_proposal()]},
        document_id="doc-A",
        revision_id="revision-2",
    )
    assert snapshot is not None
    assert snapshot["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"
    action = snapshot["proposed_actions"][0]
    assert action["source_evidence"]["revision_id"] == "revision-2"
    assert action["source_evidence"]["verification"] == "REQUIRES_SOURCE_VALIDATION"
    assert action["owner"] is None
    assert action["due_date"] is None


def test_n11_snapshot_refuses_missing_or_unreviewed_proposals():
    assert decision_snapshot_for_persistence({}, document_id=None, revision_id=None) is None
    assert decision_snapshot_for_persistence(
        {"proposed_actions": [{**_proposal(), "status": "APPROVED"}]},
        document_id="doc-A",
        revision_id=None,
    ) is None


def test_n17_resume_content_keeps_only_proposal_and_exact_revision():
    content = MaterializationContent.from_state({
        "document_id": "doc-A",
        "document_revision_id": "revision-2",
        "extracted_risks": [],
        "extracted_wbs": [],
        "decision_package": {"proposed_actions": [_proposal()]},
    })
    assert content.decision_snapshot["revision_id"] == "revision-2"
    assert content.decision_snapshot["proposed_actions"][0]["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"


def test_n17_fenced_artifact_without_proposal_cannot_invent_one():
    content = MaterializationContent.from_artifact(
        {"document_id": "doc-A", "extracted_risks": []},
        {},
    )
    assert not content.decision_snapshot


def test_n11_artifact_roundtrip_keeps_pending_proposals_unapproved():
    artifact = build_document_artifact({
        "document_id": "doc-A",
        "document_revision_id": "revision-2",
        "doc_type": "contract",
        "decision_package": {"proposed_actions": [_proposal()]},
    })
    assert artifact.decision_snapshot is not None
    assert artifact.decision_snapshot["revision_id"] == "revision-2"
    restored = MaterializationContent.from_artifact(artifact.model_dump(mode="json"), {})
    assert restored.decision_snapshot["proposed_actions"][0]["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"
    assert restored.decision_snapshot["proposed_actions"][0]["owner"] is None


def test_legacy_artifact_has_no_spurious_decisions():
    artifact = build_document_artifact({"document_id": "doc-A", "doc_type": "contract"})
    assert artifact.decision_snapshot is None


def test_live_n4_candidate_with_mitigation_becomes_projectgraph_artifact():
    """The actual N4 adapter output has fields forbidden by frozen RiskItem."""
    n4_candidate = {
        "title": "Late commissioning milestone",
        "description": "Completion is after the contractual deadline",
        "summary": "Risk of liquidated damages",
        "category": "SCHEDULE",
        "probability": "HIGH",
        "impact": "HIGH",
        "mitigation_suggestion": "Reconcile project plan with contract before approval",
        "risk_score": 9,
        "immediate_alert": True,
        "source_quote": "Completion date is June",
        "source_text_snippet": "Completion date is June",
        "clause_ref": "8.2",
    }
    artifact = build_document_artifact({
        "document_id": "doc-A",
        "document_revision_id": "revision-2",
        "doc_type": "contract",
        "extracted_risks": [n4_candidate],
        "decision_package": {"proposed_actions": [_proposal()]},
    })
    assert len(artifact.extracted_risks) == 1
    risk = artifact.extracted_risks[0]
    assert risk.title == n4_candidate["title"]
    assert risk.impact.value == "HIGH"
    # An unverified model quote never becomes trusted document evidence.
    assert risk.source_quote is None
    assert risk.source_quote_status == "REQUIRES_SOURCE_VALIDATION"
    # Mitigation is not silently lost: it remains a proposed N11 decision.
    assert artifact.decision_snapshot is not None
    assert artifact.decision_snapshot["proposed_actions"][0]["proposed_action"]
    restored = MaterializationContent.from_artifact(artifact.model_dump(mode="json"), {})
    assert restored.decision_snapshot["proposed_actions"][0]["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"


def test_n11_precedes_n17_in_executable_graph():
    """N17-first topology silently wrote analyses before decisions existed."""
    edges = set(build_workflow().edges)
    assert ("knowledge_graph", "decision_intelligence") in edges
    assert ("decision_intelligence", "save_to_db") in edges
    assert ("save_to_db", "final_assembler") in edges
    assert ("save_to_db", "decision_intelligence") not in edges


def test_real_n11_package_exists_before_n17_snapshot():
    """N4's live mitigation survives N11->N17, still pending human review."""
    state = {
        "project_id": "p1",
        "document_id": "doc-A",
        "document_revision_id": "revision-2",
        "extracted_risks": [{
            "title": "Late EPC completion",
            "impact": "HIGH",
            "mitigation_suggestion": "Align schedule milestone with contracted handover date",
            "clause_ref": "8.2",
        }],
        "messages": [],
        "node_results": [],
    }
    after_n11 = asyncio.run(decision_intelligence_node(state))
    snapshot = MaterializationContent.from_state(after_n11).decision_snapshot
    assert len(snapshot["proposed_actions"]) == 1
    assert snapshot["proposed_actions"][0]["source_evidence"]["document_id"] == "doc-A"
    assert snapshot["proposed_actions"][0]["source_evidence"]["revision_id"] == "revision-2"
    assert snapshot["proposed_actions"][0]["proposed_action"] == (
        "Align schedule milestone with contracted handover date"
    )
    assert snapshot["proposed_actions"][0]["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"

def test_live_n4_mitigation_passes_to_n11_and_n17():
    """Regression: strict RiskItem must not strip N4's real proposal."""
    mitigation = "Reconcile commissioning milestones with contract and control delay penalties"
    candidate = {
        "title": "Delay in commissioning",
        "description": "A contractual milestone is at risk",
        "category": "SCHEDULE",
        "impact": "HIGH",
        "probability": "HIGH",
        "mitigation_suggestion": mitigation,
        "source_quote": None,
        "clause_ref": "8.2",
    }
    risk = _risk_contract_payload(candidate, "Example synthetic EPC source")
    assert risk["mitigation_suggestion"] == mitigation
    state = {
        "project_id": "test-project",
        "document_id": "test-document",
        "document_revision_id": "test-revision",
        "extracted_risks": [risk],
        "messages": [],
        "node_results": [],
    }
    after_n11 = asyncio.run(decision_intelligence_node(state))
    proposals = after_n11["decision_package"]["proposed_actions"]
    assert len(proposals) == 1
    assert proposals[0]["proposed_action"] == mitigation
    assert proposals[0]["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"

    materialized = MaterializationContent.from_state(after_n11)
    proposal = materialized.decision_snapshot["proposed_actions"][0]
    assert proposal["proposed_action"] == mitigation
    assert proposal["source_evidence"]["revision_id"] == "test-revision"
    assert proposal["status"] == "PROPOSED_REQUIRES_HUMAN_REVIEW"

    artifact = build_document_artifact({**after_n11, "doc_type": "contract"})
    assert artifact.extracted_risks[0].mitigation_suggestion == mitigation
