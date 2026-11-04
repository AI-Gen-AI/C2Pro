"""Focused CORE pilot contract: N11 proposal persistence (no approvals invented)."""

from src.analysis.application.trusted_materialization import MaterializationContent
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
