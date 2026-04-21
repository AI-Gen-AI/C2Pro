"""
LangGraph nodes (N3–N5, N9, N12–N14, N17).

Thin adapter wrappers — every node now only (1) reads from the LangGraph
state, (2) invokes a use case or domain service, and (3) writes results
back to the state. Business logic and LLM prompts live under
`src.analysis.domain` / `src.analysis.application`.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 3.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from src.analysis.adapters.graph.dependencies import (
    get_ai_service,
    get_hitl_service_for_graph,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.application.classify_document_use_case import (
    ClassifyDocumentCommand,
    ClassifyDocumentUseCase,
)
from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand,
    CritiqueExtractionUseCase,
)
from src.analysis.domain.ai_extraction import (
    DeterministicRiskRulesService,
    DeterministicWbsRulesService,
)
from src.core.database import get_session_with_tenant

# Stateless domain services (reusable across requests)
_risk_rules = DeterministicRiskRulesService()
_wbs_rules = DeterministicWbsRulesService()


# ── Backwards-compatible shims ──────────────────────────────────────────────
# Kept only because external tests (TS-ADP-GRAPH-DI-001) still import them.


async def _classify_doc_type(text: str, tenant_id: str | None) -> str:
    use_case = ClassifyDocumentUseCase(ai=get_ai_service(tenant_id))
    return await use_case.execute(ClassifyDocumentCommand(text=text))


def _deterministic_contract_risks(text: str) -> list[dict[str, Any]]:
    return _risk_rules.extract(text)


def _deterministic_wbs_items(text: str) -> list[dict[str, Any]]:
    return _wbs_rules.extract(text)


# ── N3 — Router ─────────────────────────────────────────────────────────────


async def router_node(state: ProjectState) -> ProjectState:
    """N3 — Delegates doc-type classification to ClassifyDocumentUseCase."""
    use_case = ClassifyDocumentUseCase(ai=get_ai_service(state.get("tenant_id")))
    doc_type = await use_case.execute(
        ClassifyDocumentCommand(
            text=state["document_text"],
            current_doc_type=state.get("doc_type"),
        )
    )
    state["doc_type"] = doc_type
    state["messages"].append(AIMessage(content=f"Router doc_type={doc_type}"))
    return state


# ── N4 — Risk Extractor ─────────────────────────────────────────────────────


async def risk_extractor_node(state: ProjectState) -> ProjectState:
    """N4 — Extract risks via RiskExtractionTool (AI) or deterministic rules (mock)."""
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        state["extracted_risks"] = _risk_rules.extract(state.get("document_text", ""))
        state["messages"].append(
            AIMessage(content=f"Risk extractor mock mode: {len(state['extracted_risks'])} risks")
        )
        return state

    from src.core.ai.tools import get_tool

    return await get_tool("risk_extraction", version="1.0")(state)


# ── N5 — WBS Extractor ──────────────────────────────────────────────────────


async def wbs_extractor_node(state: ProjectState) -> ProjectState:
    """N5 — Extract WBS items via WBSExtractionTool (AI) or deterministic rules (mock)."""
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        state["extracted_wbs"] = _wbs_rules.extract(state.get("document_text", ""))
        state["messages"].append(
            AIMessage(content=f"WBS extractor mock mode: {len(state['extracted_wbs'])} items")
        )
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
    """N12 — Delegates critique + evaluation to CritiqueExtractionUseCase."""
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        state["confidence_score"] = 0.95  # Mock confidence
        state["retry_count"] = 0
        state["critique_notes"] = "Mock critique: Extraction quality is good."
        state["human_approval_required"] = False
        state["messages"].append(AIMessage(content="Critique mock mode: passed."))
        return state

    use_case = CritiqueExtractionUseCase(ai=get_ai_service(state.get("tenant_id")))
    result = await use_case.execute(
        CritiqueExtractionCommand(
            extracted_risks=state["extracted_risks"],
            extracted_wbs=state["extracted_wbs"],
            doc_type=state.get("doc_type"),
            retry_count=state["retry_count"],
        )
    )

    state["confidence_score"] = result.confidence
    state["retry_count"] = result.retry_count
    state["critique_notes"] = result.critique_notes
    state["human_approval_required"] = result.human_approval_required
    state["messages"].append(
        AIMessage(
            content=(
                f"Critique status={result.status} confidence={result.confidence:.2f} "
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
