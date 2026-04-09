"""
Report and decision package assembly domain services.

Pure data transformation — no framework dependencies.
Refers to TASK-IMPL-010.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    coherence_score: int | float
    confidence_score: float
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


@dataclass(frozen=True)
class DecisionPackageInput:
    """Input data for decision package assembly."""

    coherence_score: int | float
    extracted_risks: list[dict[str, Any]]
    extracted_stakeholders: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    bom_items: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    citation_validation_passed: bool
    human_feedback: str


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
            "human_approval_required": inp.human_approval_required,
            "human_feedback": inp.human_feedback,
        }


class DecisionPackageAssemblyService:
    """Assembles a decision package from upstream analysis results."""

    def assemble(self, inp: DecisionPackageInput) -> dict[str, Any]:
        return {
            "coherence_score": inp.coherence_score,
            "risks": inp.extracted_risks,
            "stakeholders": inp.extracted_stakeholders,
            "wbs_items": inp.extracted_wbs,
            "bom_items": inp.bom_items,
            "evidence_links": [],
            "citations": [c.get("quote", "") for c in inp.citations],
            "citation_validation_passed": inp.citation_validation_passed,
            "approved_by": "human_reviewer" if inp.human_feedback else None,
            "approved_at": None,
        }
