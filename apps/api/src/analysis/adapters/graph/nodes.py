from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.schema import ProjectState

DOC_TYPES: tuple[str, ...] = ("contract", "technical_spec", "budget")

ROUTER_SYSTEM_PROMPT = """
Clasifica el documento en uno de estos tipos: contract, technical_spec, budget.
Devuelve SOLO un JSON con el formato: {"doc_type": "..."}.
""".strip()

CRITIQUE_SYSTEM_PROMPT = """
Eres un revisor senior de calidad.
Evalua si la extraccion es correcta, completa y con referencias claras.
Devuelve SOLO un JSON con el formato:
{"status": "OK"|"RETRY", "notes": "..."}.
""".strip()


def _average_confidence(items: list[dict[str, Any]]) -> float:
    confidences = [item.get("confidence") for item in items if isinstance(item.get("confidence"), (int, float))]
    if not confidences:
        return 0.0 if not items else 0.9
    return float(sum(confidences)) / float(len(confidences))


def _fallback_doc_type(text: str) -> str:
    normalized = text.lower()
    if any(keyword in normalized for keyword in ("contrato", "clausula", "adenda", "partes", "obligaciones")):
        return "contract"
    if any(keyword in normalized for keyword in ("presupuesto", "capex", "opex", "coste", "costo")):
        return "budget"
    return "technical_spec"


def _augment_document(text: str, critique_notes: str, human_feedback: str) -> str:
    additions = []
    if critique_notes:
        additions.append(f"NOTAS_CRITICAS: {critique_notes}")
    if human_feedback:
        additions.append(f"FEEDBACK_HUMANO: {human_feedback}")
    if not additions:
        return text
    return f"{text}\n\n" + "\n".join(additions)


async def _classify_doc_type(text: str, tenant_id: str | None) -> str:
    from src.analysis.adapters.ai.anthropic_client import AIService

    service = AIService(tenant_id=tenant_id)
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
    from src.analysis.adapters.ai.anthropic_client import AIService

    service = AIService(tenant_id=tenant_id)
    try:
        payload = await service.run_extraction(
            CRITIQUE_SYSTEM_PROMPT,
            f"Tipo de documento: {doc_type}\nResultados: {items}",
        )
        if isinstance(payload, dict):
            status = str(payload.get("status", "")).upper()
            notes = str(payload.get("notes", "")).strip()
            if status in {"OK", "RETRY"}:
                return {"status": status, "notes": notes}
    except Exception:
        pass
    return {"status": "RETRY", "notes": "Critica automatica no concluyente."}


async def router_node(state: ProjectState) -> ProjectState:
    if state.get("doc_type") in DOC_TYPES:
        return state
    doc_type = await _classify_doc_type(state["document_text"], state.get("tenant_id"))
    state["doc_type"] = doc_type
    state["messages"].append(AIMessage(content=f"Router doc_type={doc_type}"))
    return state


async def risk_extractor_node(state: ProjectState) -> ProjectState:
    """
    Extract risks using RiskExtractionTool.

    The tool handles:
    - Input extraction from state (with critique/feedback augmentation)
    - Prompt rendering
    - LLM call via AnthropicWrapper
    - Output parsing and validation
    - State injection
    """
    from src.core.ai.tools import get_tool

    tool = get_tool("risk_extraction", version="1.0")
    return await tool(state)


async def wbs_extractor_node(state: ProjectState) -> ProjectState:
    """
    Extract WBS items using WBSExtractionTool.

    The tool handles:
    - Input extraction from state (with critique/feedback augmentation)
    - Prompt rendering
    - LLM call via AnthropicWrapper
    - Output parsing and validation to typed WBSItemOutput models
    - State injection
    """
    from src.core.ai.tools import get_tool

    tool = get_tool("wbs_extraction", version="1.0")
    return await tool(state)


async def budget_parser_node(state: ProjectState) -> ProjectState:
    """N9 — Delegates to the extended budget parser with BOM extraction."""
    from src.analysis.adapters.graph.nodes_extended import budget_parser_extended_node

    return await budget_parser_extended_node(state)


async def critique_node(state: ProjectState) -> ProjectState:
    items = state["extracted_risks"] if state["extracted_risks"] else state["extracted_wbs"]
    state["confidence_score"] = _average_confidence(items)
    critique = await _critique_extraction(
        items=items,
        doc_type=state.get("doc_type") or "unknown",
        tenant_id=state.get("tenant_id"),
    )
    status = critique["status"]
    if status == "RETRY":
        state["critique_notes"] = critique["notes"]
        state["retry_count"] += 1
    else:
        state["critique_notes"] = ""
    # In mock mode, skip HITL to allow full pipeline testing
    import os
    skip_hitl_in_mock = os.getenv("C2PRO_AI_MOCK", "0") == "1"

    state["human_approval_required"] = (
        not skip_hitl_in_mock and
        (state["confidence_score"] < 0.8 or (status == "RETRY" and state["retry_count"] >= 2))
    )
    state["messages"].append(
        AIMessage(
            content=(
                f"Critique status={status} confidence={state['confidence_score']:.2f} "
                f"retry_count={state['retry_count']}"
            )
        )
    )
    return state


async def human_interrupt_node(state: ProjectState) -> ProjectState:
    from langgraph.types import interrupt

    from src.modules.hitl.domain.entities import ImpactLevel

    # Route item through the real HITL service when a tenant is available.
    tenant_id = state.get("tenant_id")
    if tenant_id:
        try:
            from src.core.database import get_session_with_tenant
            from src.modules.hitl.adapters.persistence.repository import (
                SqlAlchemyReviewQueueRepository,
            )
            from src.modules.hitl.adapters.notifications.log_notification_service import (
                LogNotificationService,
            )
            from src.modules.hitl.application.ports import HumanInTheLoopService
            from src.modules.hitl.domain.services import ConfidenceRouter

            impact = (
                ImpactLevel.HIGH
                if state.get("confidence_score", 0) < 0.5
                else ImpactLevel.MEDIUM
            )

            async with get_session_with_tenant(UUID(tenant_id)) as session:
                repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=UUID(tenant_id))
                service = HumanInTheLoopService(
                    review_queue_repo=repo,
                    notification_service=LogNotificationService(),
                    confidence_router=ConfidenceRouter(),
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

    # Always fire the LangGraph interrupt so the workflow pauses.
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


async def save_to_db_node(state: ProjectState) -> ProjectState:
    if not state.get("tenant_id"):
        state["messages"].append(AIMessage(content="Missing tenant_id; skipping persistence."))
        return state

    from src.core.database import get_session_with_tenant
    from sqlalchemy import delete
    from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
    from src.analysis.adapters.persistence.models import Alert, Analysis
    from src.analysis.domain.enums import AnalysisStatus, AnalysisType
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
    from src.procurement.adapters.persistence.models import WBSItemORM

    project_id = UUID(state["project_id"])
    tenant_id = UUID(state["tenant_id"])
    analysis_type = AnalysisType.RISK if state["extracted_risks"] else AnalysisType.SCHEDULE

    async with get_session_with_tenant(tenant_id) as session:
        repo = SqlAlchemyAnalysisRepository(session)
        wbs_repo = SQLAlchemyWBSRepository(session)
        alerts_count = len(state.get("extracted_risks", []))
        analysis = Analysis(
            project_id=project_id,
            analysis_type=analysis_type,
            status=AnalysisStatus.COMPLETED,
            coherence_score=state.get("coherence_score"),
            coherence_breakdown=state.get("coherence_breakdown"),
            alerts_count=alerts_count,
            completed_at=datetime.utcnow(),
            result_json={"risks": state["extracted_risks"], "wbs": state["extracted_wbs"]},
        )
        await repo.add_analysis(analysis)
        await repo.flush()

        if state["extracted_risks"]:
            alerts = []
            for item in state["extracted_risks"]:
                severity = _map_risk_severity(item)

                alerts.append(
                    Alert(
                        project_id=project_id,
                        analysis_id=analysis.id,
                        severity=severity,
                        title=item.get("summary") or item.get("title") or "Risk identified",
                        description=item.get("description") or "Risk detected by AI extraction.",
                        category="risk",
                        impact_level=item.get("impact_level"),
                        alert_metadata={"confidence": item.get("confidence"), "raw": item},
                    )
                )
            await repo.add_alerts(alerts)

        if state["extracted_wbs"]:
            # Re-analysis is expected in real usage; replace previous WBS snapshot
            # for this project to avoid duplicate (project_id, code) conflicts.
            await session.execute(
                delete(WBSItemORM).where(WBSItemORM.project_id == project_id)
            )
            await wbs_repo.bulk_create_from_dicts(project_id, state["extracted_wbs"])

        state["analysis_id"] = str(analysis.id)
        state["messages"].append(
            AIMessage(content=f"Persisted analysis {analysis.id} (type={analysis_type.value}).")
        )
        await repo.commit()
    return state


def _next_after_critique(state: ProjectState) -> Literal[
    "risk_extractor",
    "wbs_extractor",
    "budget_parser",
    "human_interrupt",
    "save_to_db",
]:
    if state["human_approval_required"]:
        return "human_interrupt"
    if state["critique_notes"] and state["retry_count"] > 0:
        if state["retry_count"] <= 2:
            if state["doc_type"] == "contract":
                return "risk_extractor"
            if state["doc_type"] == "budget":
                return "budget_parser"
            return "wbs_extractor"
    return "save_to_db"


def _risk_item_to_dict(risk) -> dict[str, Any]:
    return {
        "category": getattr(risk, "category", None).value if getattr(risk, "category", None) else None,
        "title": getattr(risk, "title", None),
        "summary": getattr(risk, "summary", None),
        "description": getattr(risk, "description", None),
        "probability": getattr(risk, "probability", None).value if getattr(risk, "probability", None) else None,
        "impact": getattr(risk, "impact", None).value if getattr(risk, "impact", None) else None,
        "mitigation_suggestion": getattr(risk, "mitigation_suggestion", None),
        "source_quote": getattr(risk, "source_quote", None),
        "source_text_snippet": getattr(risk, "source_text_snippet", None),
        "risk_score": getattr(risk, "risk_score", 0),
        "immediate_alert": getattr(risk, "immediate_alert", False),
    }


def _map_risk_severity(item: dict[str, Any]):
    from src.shared_kernel.enums import AlertSeverity

    severity_source = item.get("severity") or item.get("impact") or "low"
    severity_value = str(severity_source).lower()
    for candidate in AlertSeverity:
        if candidate.value == severity_value:
            return candidate
    return AlertSeverity.LOW
