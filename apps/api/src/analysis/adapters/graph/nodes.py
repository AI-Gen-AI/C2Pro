"""
LangGraph nodes (N3–N5, N9, N12–N14, N17).

Thin adapter wrappers — business logic lives in domain services and
application use cases. Each node is < 50 lines.

Refers to TASK-IMPL-010.8–.14.
"""

from __future__ import annotations

import os
import re
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from src.analysis.adapters.graph.dependencies import (
    get_ai_service,
    get_hitl_service_for_graph,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService
from src.analysis.domain.prompts import (
    CRITIQUE_SYSTEM_PROMPT,
    DOC_TYPES,
    ROUTER_SYSTEM_PROMPT,
)
from src.core.database import get_session_with_tenant

# Stateless domain service (reusable across requests)
_critique_evaluator = CritiqueEvaluationService()


# ── Adapter helpers (AI calls — cannot live in domain) ──────────────────────


def _fallback_doc_type(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("contrato", "clausula", "contract", "clause", "obligaciones")):
        return "contract"
    if any(k in low for k in ("presupuesto", "capex", "opex", "budget", "cost")):
        return "budget"
    if any(k in low for k in ("cronograma", "plazo", "hito", "schedule", "milestone", "gantt")):
        return "schedule"
    return "technical_spec"


async def _classify_doc_type(text: str, tenant_id: str | None) -> str:
    service = get_ai_service(tenant_id)
    try:
        payload = await service.run_extraction(ROUTER_SYSTEM_PROMPT, text)
        if isinstance(payload, dict):
            candidate = str(payload.get("doc_type", "")).strip().lower()
            if candidate in DOC_TYPES:
                return candidate
    except Exception:
        pass
    return _fallback_doc_type(text)


async def _critique_extraction(
    *,
    items: list[dict[str, Any]],
    doc_type: str,
    tenant_id: str | None,
) -> dict[str, str]:
    service = get_ai_service(tenant_id)
    try:
        payload = await service.run_extraction(
            CRITIQUE_SYSTEM_PROMPT,
            f"Document type: {doc_type}\nExtraction results: {items}",
        )
        if isinstance(payload, dict):
            status = str(payload.get("status", "")).upper()
            notes = str(payload.get("notes", "")).strip()
            if status in {"OK", "RETRY"}:
                return {"status": status, "notes": notes}
    except Exception:
        pass
    return {"status": "RETRY", "notes": "Automatic critique inconclusive."}


# ── N3 — Router ─────────────────────────────────────────────────────────────


async def router_node(state: ProjectState) -> ProjectState:
    """N3 — Classify document type via AI with keyword fallback."""
    if state.get("doc_type") in DOC_TYPES:
        return state
    doc_type = await _classify_doc_type(state["document_text"], state.get("tenant_id"))
    state["doc_type"] = doc_type
    state["messages"].append(AIMessage(content=f"Router doc_type={doc_type}"))
    return state


# ── N4 — Risk Extractor ─────────────────────────────────────────────────────


def _deterministic_contract_risks(text: str) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    lower = text.lower()
    if "penalt" in lower or "% for delay" in lower or "delay" in lower:
        risks.append(
            {
                "category": "LEGAL",
                "title": "Delay penalty exposure",
                "summary": "Contract includes delay penalties.",
                "description": "The contract contains penalty language linked to delay or late completion.",
                "probability": "MEDIUM",
                "impact": "HIGH",
                "mitigation_suggestion": "Validate schedule buffers, milestone logic, and penalty caps before execution.",
                "source_quote": "Daily penalty 2% for delay.",
                "source_text_snippet": "Daily penalty 2% for delay.",
                "risk_score": 6,
                "immediate_alert": False,
                "confidence": 0.82,
            }
        )
    if re.search(r"\b30\s+days\b", lower) and "payment" in lower:
        risks.append(
            {
                "category": "FINANCIAL",
                "title": "Payment term cash-flow risk",
                "summary": "Payment depends on certified milestones within a defined term.",
                "description": "Cash flow may depend on milestone certification and payment timing discipline.",
                "probability": "MEDIUM",
                "impact": "MEDIUM",
                "mitigation_suggestion": "Check certification workflow, invoice timing, and interim financing assumptions.",
                "source_quote": "Payment subject to certified milestones within 30 days.",
                "source_text_snippet": "Payment subject to certified milestones within 30 days.",
                "risk_score": 4,
                "immediate_alert": False,
                "confidence": 0.79,
            }
        )
    if "warranty" in lower:
        risks.append(
            {
                "category": "QUALITY",
                "title": "Warranty obligation exposure",
                "summary": "Warranty obligations extend post-handover liability.",
                "description": "The contract imposes a warranty period that may require post-completion corrections.",
                "probability": "MEDIUM",
                "impact": "MEDIUM",
                "mitigation_suggestion": "Confirm defect response process, retention terms, and warranty reserve assumptions.",
                "source_quote": "Warranty period is 24 months.",
                "source_text_snippet": "Warranty period is 24 months.",
                "risk_score": 4,
                "immediate_alert": False,
                "confidence": 0.77,
            }
        )
    return risks


async def risk_extractor_node(state: ProjectState) -> ProjectState:
    """N4 — Extract risks via RiskExtractionTool."""
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        state["extracted_risks"] = _deterministic_contract_risks(state.get("document_text", ""))
        state["messages"].append(AIMessage(content=f"Risk extractor mock mode: {len(state['extracted_risks'])} risks"))
        return state

    from src.core.ai.tools import get_tool

    return await get_tool("risk_extraction", version="1.0")(state)


# ── N5 — WBS Extractor ──────────────────────────────────────────────────────


def _deterministic_wbs_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    lower = text.lower()
    if any(term in lower for term in ["scope", "works", "materials", "inspection", "handover"]):
        items.append(
            {
                "code": "1.1",
                "name": "Contract scope execution",
                "description": "Execution of the contract scope including materials, inspection, testing, and handover.",
                "item_type": "work_package",
                "confidence": 0.8,
            }
        )
    if "deadline" in lower or "completion" in lower:
        items.append(
            {
                "code": "1.2",
                "name": "Completion milestone control",
                "description": "Control of delivery and completion milestones against contractual dates.",
                "item_type": "activity",
                "confidence": 0.78,
            }
        )
    return items


async def wbs_extractor_node(state: ProjectState) -> ProjectState:
    """N5 — Extract WBS items via WBSExtractionTool."""
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        state["extracted_wbs"] = _deterministic_wbs_items(state.get("document_text", ""))
        state["messages"].append(AIMessage(content=f"WBS extractor mock mode: {len(state['extracted_wbs'])} items"))
        return state

    from src.core.ai.tools import get_tool

    return await get_tool("wbs_extraction", version="1.0")(state)


# ── N9 — Budget Parser (delegates to extended) ──────────────────────────────


async def budget_parser_node(state: ProjectState) -> ProjectState:
    """N9 — Delegates to the extended budget parser with BOM extraction."""
    from src.analysis.adapters.graph.nodes_extended import budget_parser_extended_node

    return await budget_parser_extended_node(state)


# ── N12 — Critique ──────────────────────────────────────────────────────────


async def critique_node(state: ProjectState) -> ProjectState:
    """N12 — Critique extraction quality and determine HITL routing.

    Delegates confidence calculation and evaluation to CritiqueEvaluationService.
    """
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        state["confidence_score"] = 0.95 # Mock confidence
        state["retry_count"] = 0
        state["critique_notes"] = "Mock critique: Extraction quality is good."
        state["human_approval_required"] = False
        state["messages"].append(AIMessage(content="Critique mock mode: passed."))
        return state

    items = state["extracted_risks"] if state["extracted_risks"] else state["extracted_wbs"]
    confidence = _critique_evaluator.calculate_confidence(items)
    state["confidence_score"] = confidence

    critique = await _critique_extraction(
        items=items,
        doc_type=state.get("doc_type") or "unknown",
        tenant_id=state.get("tenant_id"),
    )

    result = _critique_evaluator.evaluate_critique(
        critique_status=critique["status"],
        critique_notes=critique["notes"],
        confidence=confidence,
        retry_count=state["retry_count"],
    )

    state["retry_count"] = result.retry_count
    state["critique_notes"] = result.critique_notes
    state["human_approval_required"] = result.human_approval_required
    state["messages"].append(
        AIMessage(
            content=(
                f"Critique status={critique['status']} confidence={confidence:.2f} "
                f"retry_count={result.retry_count}"
            )
        )
    )
    return state


# ── N13 — Human Interrupt (HITL) ────────────────────────────────────────────


async def human_interrupt_node(state: ProjectState) -> ProjectState:
    """N13 — Route through HITL service and raise LangGraph Interrupt.

    Delegates domain routing to HumanInTheLoopService; interrupt stays here.
    """
    from src.modules.hitl.domain.entities import ImpactLevel

    tenant_id = state.get("tenant_id")
    if tenant_id:
        try:
            impact = (
                ImpactLevel.HIGH
                if state.get("confidence_score", 0) < 0.5
                else ImpactLevel.MEDIUM
            )
            async with get_session_with_tenant(UUID(tenant_id)) as session:
                service = get_hitl_service_for_graph(
                    session=session, tenant_id=UUID(tenant_id),
                )
                await service.route_for_review(
                    item_id=UUID(state["document_id"]),
                    item_type=state.get("doc_type") or "unknown",
                    confidence=state.get("confidence_score", 0.0),
                    impact_level=impact,
                    item_data={
                        "project_id": state["project_id"],
                        "document_id": state["document_id"],
                        "doc_type": state.get("doc_type"),
                        "retry_count": state.get("retry_count", 0),
                        "critique_notes": state.get("critique_notes", ""),
                    },
                )
        except Exception:
            import structlog

            structlog.get_logger().warning(
                "hitl_routing_failed_falling_back_to_interrupt",
                document_id=state.get("document_id"),
                exc_info=True,
            )

    interrupt(
        {
            "reason": "approval_required",
            "project_id": state["project_id"],
            "document_id": state["document_id"],
            "doc_type": state["doc_type"],
            "retry_count": state["retry_count"],
        }
    )
    state["human_approval_required"] = True
    state["messages"].append(AIMessage(content="Human approval requested."))
    return state


# ── N17 — Save to DB ────────────────────────────────────────────────────────


async def save_to_db_node(state: ProjectState) -> ProjectState:
    """N17 — Persist analysis, alerts, and WBS via PersistAnalysisUseCase."""
    if not state.get("tenant_id"):
        state["messages"].append(AIMessage(content="Missing tenant_id; skipping persistence."))
        return state

    from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
    from src.analysis.application.persist_analysis_use_case import (
        PersistAnalysisCommand,
        PersistAnalysisUseCase,
    )
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository

    tenant_id = UUID(state["tenant_id"])
    async with get_session_with_tenant(tenant_id) as session:
        result = await PersistAnalysisUseCase(
            analysis_repo=SqlAlchemyAnalysisRepository(session),
            wbs_repo=SQLAlchemyWBSRepository(session),
            session=session,
        ).execute(
            PersistAnalysisCommand(
                project_id=UUID(state["project_id"]),
                tenant_id=tenant_id,
                extracted_risks=state.get("extracted_risks", []),
                extracted_wbs=state.get("extracted_wbs", []),
                coherence_score=state.get("coherence_score", 0),
                coherence_breakdown=state.get("coherence_breakdown", {}),
            )
        )

    state["analysis_id"] = str(result.analysis_id)
    state["messages"].append(AIMessage(content=f"Persisted analysis {result.analysis_id}."))
    return state
