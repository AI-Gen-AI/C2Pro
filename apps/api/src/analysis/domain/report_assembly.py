"""
Report and decision package assembly domain services.

Pure data transformation — no framework dependencies.
Refers to TASK-IMPL-010.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ReportInput:
    """Input data for final report assembly."""

    project_id: str
    document_id: str
    doc_type: str
    document_category: str
    analysis_id: str | None
    extracted_risks: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    extracted_stakeholders: list[dict[str, Any]]
    bom_items: list[dict[str, Any]]
    coherence_score: int | float | None
    coherence_score_version: str | None
    confidence_score: float | None
    citation_validation_passed: bool
    pii_redactions: list[dict[str, Any]]
    raci_matrix: list[dict[str, Any]]
    coherence_breakdown: dict[str, Any]
    citations: list[dict[str, Any]]
    knowledge_graph_nodes: list[dict[str, Any]]
    knowledge_graph_edges: list[dict[str, Any]]
    decision_package: dict[str, Any]
    human_approval_required: bool
    human_feedback: str
    # Original, revision-bound source observations. Not an approved baseline.
    project_source_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionPackageInput:
    """Input data for decision package assembly."""

    coherence_score: int | float | None
    coherence_score_version: str | None
    extracted_risks: list[dict[str, Any]]
    extracted_stakeholders: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    bom_items: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    citation_validation_passed: bool
    human_feedback: str
    project_source_evidence: dict[str, Any] = field(default_factory=dict)


def _proposed_risk_actions(risks: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Show model-supported suggestions, not invented owners or approved tasks."""
    actions: list[dict[str, Any]] = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        mitigation = risk.get("mitigation_suggestion")
        title = risk.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(mitigation, str) or not mitigation.strip():
            continue
        impact = str(risk.get("impact") or "").upper()
        priority = (
            "P1" if impact == "CRITICAL"
            else "P2" if impact == "HIGH"
            else "P3" if impact in {"LOW", "MEDIUM"}
            else "UNASSESSED"
        )
        evidence = {
            "document_id": risk.get("document_id"),
            "clause_ref": risk.get("clause_ref"),
            "source_quote": risk.get("source_quote"),
            "verification": "REQUIRES_SOURCE_VALIDATION",
        }
        actions.append({
            "title": title.strip(),
            "proposed_action": mitigation.strip(),
            "priority_proposal": priority,
            "priority_basis": "model_extracted_risk_impact" if priority != "UNASSESSED" else "unassessed",
            "risk_impact": impact if impact else None,
            "owner": None,
            "due_date": None,
            "status": "PROPOSED_REQUIRES_HUMAN_REVIEW",
            "source_evidence": evidence,
        })
        if len(actions) >= limit:
            break
    return actions



def decision_snapshot_for_persistence(
    package: Mapping[str, Any] | None,
    *,
    document_id: str | None,
    revision_id: str | None,
) -> dict[str, Any] | None:
    """Preserve only N11's *proposals* with their source identity.

    This is not a decision approval, validated citation, or trusted baseline.
    A missing revision remains missing (never silently attributed to latest).
    """
    if not isinstance(package, Mapping):
        return None
    raw_actions = package.get("proposed_actions")
    if not isinstance(raw_actions, list):
        return None
    actions: list[dict[str, Any]] = []
    for action in raw_actions:
        if not isinstance(action, dict) or not action.get("proposed_action"):
            continue
        if action.get("status") != "PROPOSED_REQUIRES_HUMAN_REVIEW":
            continue
        source = action.get("source_evidence")
        source = source if isinstance(source, dict) else {}
        source_document = source.get("document_id") or document_id
        source_revision = source.get("revision_id") or (
            revision_id if source_document == document_id else None
        )
        actions.append({
            "title": action.get("title"),
            "proposed_action": action["proposed_action"],
            "priority_proposal": action.get("priority_proposal") or "UNASSESSED",
            "priority_basis": action.get("priority_basis") or "unassessed",
            "risk_impact": action.get("risk_impact"),
            "owner": None,  # N11 does not establish decision authority.
            "due_date": None,
            "status": "PROPOSED_REQUIRES_HUMAN_REVIEW",
            "source_evidence": {
                "document_id": source_document,
                "revision_id": source_revision,
                "clause_ref": source.get("clause_ref"),
                "source_quote": source.get("source_quote"),
                "verification": "REQUIRES_SOURCE_VALIDATION",
            },
        })
        if len(actions) == 5:
            break
    if not actions:
        return None
    return {
        "status": "PROPOSED_REQUIRES_HUMAN_REVIEW",
        "document_id": document_id,
        "revision_id": revision_id,
        "proposed_actions": actions,
    }


class ReportAssemblyService:
    """Assembles all analysis results into a structured final report."""

    def assemble(self, inp: ReportInput) -> dict[str, Any]:
        return {
            "project_id": inp.project_id,
            "document_id": inp.document_id,
            "doc_type": inp.doc_type,
            "document_category": inp.document_category,
            "analysis_id": inp.analysis_id,
            "summary": {
                "total_risks": len(inp.extracted_risks),
                "total_wbs_items": len(inp.extracted_wbs),
                "total_stakeholders": len(inp.extracted_stakeholders),
                "total_bom_items": len(inp.bom_items),
                "coherence_score": inp.coherence_score,
                "coherence_score_version": inp.coherence_score_version,
                "confidence_score": inp.confidence_score,
                "citation_validation_passed": inp.citation_validation_passed,
                "pii_items_redacted": len(inp.pii_redactions),
            },
            "risks": inp.extracted_risks,
            "wbs_items": inp.extracted_wbs,
            "stakeholders": inp.extracted_stakeholders,
            "raci_matrix": inp.raci_matrix,
            "bom_items": inp.bom_items,
            "coherence_breakdown": inp.coherence_breakdown,
            "citations": inp.citations,
            "knowledge_graph": {
                "nodes": inp.knowledge_graph_nodes,
                "edges": inp.knowledge_graph_edges,
            },
            "decision_package": inp.decision_package,
            "project_source_evidence": inp.project_source_evidence,
            "human_approval_required": inp.human_approval_required,
            "human_feedback": inp.human_feedback,
        }


class DecisionPackageAssemblyService:
    """Assembles a decision package from upstream analysis results."""

    def assemble(self, inp: DecisionPackageInput) -> dict[str, Any]:
        return {
            "coherence_score": inp.coherence_score,
            "coherence_score_version": inp.coherence_score_version,
            "risks": inp.extracted_risks,
            "stakeholders": inp.extracted_stakeholders,
            "wbs_items": inp.extracted_wbs,
            "bom_items": inp.bom_items,
            # Never construct a URL without an authorized document locator.
            "evidence_links": [],
            "project_source_evidence": inp.project_source_evidence,
            "proposed_actions": _proposed_risk_actions(inp.extracted_risks),
            "citations": [c.get("quote", "") for c in inp.citations],
            "citation_validation_passed": inp.citation_validation_passed,
            "approved_by": "human_reviewer" if inp.human_feedback else None,
            "approved_at": None,
        }
