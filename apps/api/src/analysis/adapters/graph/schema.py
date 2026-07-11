from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.analysis.domain.contracts import BudgetItem, Citation, RiskItem, WbsActivity
from src.analysis.domain.documentation_health import DocumentationHealthSignal
from src.analysis.domain.node_result import NodeResult, merge_node_results

Risk = RiskItem
Task = WbsActivity
StakeholderDict = dict[str, Any]
RaciEntry = dict[str, Any]
CoherenceBreakdown = dict[str, float | None]
BomEntry = BudgetItem


class ProjectState(TypedDict):
    # ── Original fields (N3 router, N4 risk, N5 wbs, N12 critique, N13/14 HITL, N17 save) ──
    project_id: str
    document_id: str
    document_text: str
    doc_type: str
    messages: Annotated[list[BaseMessage], add_messages]
    extracted_risks: list[Risk]
    extracted_wbs: list[Task]
    confidence_score: float
    critique_notes: str
    human_feedback: str
    retry_count: int
    tenant_id: str | None
    thread_id: str | None
    analysis_id: str | None
    human_approval_required: bool
    force_full_pipeline: bool

    # ── N1: Document Ingestion ──
    document_parsed: bool
    document_category: str  # SCOPE / BUDGET / TIME / QUALITY / TECHNICAL / LEGAL

    # ── N2: PII Anonymizer ──
    anonymized_text: str
    pii_redactions: list[dict[str, Any]]

    # ── N6: Stakeholder Extractor ──
    extracted_stakeholders: list[StakeholderDict]

    # ── N7: RACI Generator ──
    raci_matrix: list[RaciEntry]

    # ── N8: Coherence Scorer ──
    coherence_score: int | float | None
    coherence_score_version: str | None
    coherence_reason: str | None
    coherence_missing_dimensions: list[str]
    coherence_breakdown: CoherenceBreakdown

    # ── N9: Budget Parser (extended) ──
    bom_items: list[BomEntry]

    # ── N10: Knowledge Graph Builder ──
    knowledge_graph_nodes: list[dict[str, Any]]
    knowledge_graph_edges: list[dict[str, Any]]

    # ── N11: Decision Intelligence ──
    decision_package: dict[str, Any]

    # ── N15: Citation Validator ──
    citations: list[Citation]
    citation_validation_passed: bool

    # ── N16: Final Assembler ──
    final_report: dict[str, Any]
    node_results: Annotated[list[NodeResult], merge_node_results]
    documentation_health_signal: DocumentationHealthSignal | None
