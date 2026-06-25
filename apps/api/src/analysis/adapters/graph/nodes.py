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

import structlog
from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from src.analysis.adapters.graph.dependencies import (
    get_ai_service,
    get_hitl_service_for_graph,
)
from src.analysis.adapters.graph.nodes_extended import (
    _failed_node_result,
    _maybe_await,
    _ok_node_result,
    _persist_node_error,
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
    CritiqueExtractionService,
    DeterministicRiskRulesService,
    DeterministicWbsRulesService,
)
from src.analysis.domain.contracts import RiskItem, WbsActivity
from src.analysis.domain.node_result import NodeResult, NodeStatus
from src.analysis.domain.prompts import DOC_TYPES
from src.core.database import get_session_with_tenant

# Stateless domain services (reusable across requests)
_risk_rules = DeterministicRiskRulesService()
_wbs_rules = DeterministicWbsRulesService()
_critique_service = CritiqueExtractionService()
logger = structlog.get_logger()
MIN_EXTRACTABLE_TEXT_CHARS = 8


def _meaningful_text_length(text: str | None) -> int:
    return len("".join((text or "").split()))


def _has_extractable_text(text: str | None) -> bool:
    return _meaningful_text_length(text) >= MIN_EXTRACTABLE_TEXT_CHARS


def _insufficient_extractable_text_message() -> str:
    return "No extractable text — document may be scanned; OCR required"


def _tool_error_detail(exc: Exception, *, max_length: int = 300) -> str:
    detail = str(exc).replace("\n", " ").strip()
    if len(detail) > max_length:
        return f"{detail[:max_length]}..."
    return detail


def _mark_risk_extraction_honest_failure(
    state: ProjectState,
    *,
    reason: str,
    exc: Exception | None = None,
    previous_confidence: float | None = None,
) -> ProjectState:
    if previous_confidence is not None:
        state["confidence_score"] = previous_confidence
    state["extracted_risks"] = []
    error_type = type(exc).__name__ if exc is not None else None
    error_detail = _tool_error_detail(exc) if exc is not None else None
    message = reason
    if error_type and error_detail:
        message = f"{reason}; {error_type}: {error_detail}"
    state["messages"].append(AIMessage(content=message))
    logger.warning(
        "risk_extraction_honest_failure",
        reason=reason,
        error_type=error_type,
        error_detail=error_detail,
        project_id=state.get("project_id"),
        document_id=state.get("document_id"),
    )
    return state


def _append_risk_extraction_summary(state: ProjectState) -> None:
    input_chars = len(state.get("document_text") or "")
    risks_emitted = len(state.get("extracted_risks") or [])
    state["messages"].append(
        AIMessage(
            content=(
                f"N4 risk_extractor: input_doc_chars={input_chars} "
                f"risks_emitted={risks_emitted}"
            )
        )
    )

_RISK_LEGACY_KEYS = {
    "summary",
    "probability",
    "mitigation_suggestion",
    "source_quote",
    "source_text_snippet",
    "risk_score",
    "immediate_alert",
}
_WBS_LEGACY_KEYS = {"item_type", "confidence"}


def _unexpected_contract_keys(
    item: dict[str, Any],
    *,
    allowed: set[str],
    legacy: set[str],
) -> set[str]:
    return set(item) - allowed - legacy


def _risk_contract_item(item: RiskItem | dict[str, Any]) -> RiskItem:
    if isinstance(item, RiskItem):
        return item
    unknown = _unexpected_contract_keys(
        item,
        allowed=set(RiskItem.model_fields),
        legacy=_RISK_LEGACY_KEYS,
    )
    if unknown:
        raise ValueError(f"risk_extractor emitted unknown contract fields: {sorted(unknown)}")
    data = {key: item[key] for key in RiskItem.model_fields if key in item}
    if not data.get("description") and item.get("summary"):
        data["description"] = item["summary"]
    if not data.get("description") and data.get("title"):
        data["description"] = data["title"]
    if not data.get("source"):
        data["source"] = item.get("source_quote") or item.get("source_text_snippet")
    if not data.get("likelihood") and item.get("probability"):
        data["likelihood"] = item["probability"]
    return RiskItem.model_validate(data)


def _risk_contract_payload(item: RiskItem | dict[str, Any]) -> dict[str, Any]:
    return _risk_contract_item(item).model_dump(mode="python")


def _wbs_contract_item(item: WbsActivity | dict[str, Any]) -> WbsActivity:
    if isinstance(item, WbsActivity):
        return item
    unknown = _unexpected_contract_keys(
        item,
        allowed=set(WbsActivity.model_fields),
        legacy=_WBS_LEGACY_KEYS,
    )
    if unknown:
        raise ValueError(f"wbs_extractor emitted unknown contract fields: {sorted(unknown)}")
    data = {key: item[key] for key in WbsActivity.model_fields if key in item}
    return WbsActivity.model_validate(data)


def _wbs_contract_payload(item: WbsActivity | dict[str, Any]) -> dict[str, Any]:
    return _wbs_contract_item(item).model_dump(mode="python")


# ── Backwards-compatible shims ──────────────────────────────────────────────
# Kept because legacy facade modules (src.ai.graph) and the TS-ADP-GRAPH-DI-001
# suite import these helpers by name and monkeypatch them at runtime.


async def _classify_doc_type(text: str, tenant_id: str | None) -> str:
    use_case = ClassifyDocumentUseCase(ai=get_ai_service(tenant_id))
    return await use_case.execute(ClassifyDocumentCommand(text=text))


async def _critique_extraction(
    *,
    items: list[dict[str, Any]],
    doc_type: str,
    tenant_id: str | None,
) -> dict[str, str]:
    result = await _critique_service.extract(
        items=items,
        doc_type=doc_type,
        ai=get_ai_service(tenant_id),
    )
    return {"status": result.status, "notes": result.notes}


def _deterministic_contract_risks(text: str) -> list[dict[str, Any]]:
    return _risk_rules.extract(text)


def _deterministic_wbs_items(text: str) -> list[dict[str, Any]]:
    return _wbs_rules.extract(text)


def _map_risk_severity(item: dict[str, Any]):
    """Map a risk dict to an AlertSeverity enum.

    Backwards-compat shim — legacy tests (tests/ai/test_risk_extractor.py)
    still import this helper by name. Production alert generation now lives
    in ``src.coherence.alert_generator.AlertGenerator``.
    """
    from src.shared_kernel.enums import AlertSeverity

    severity_source = item.get("severity") or item.get("impact") or "low"
    severity_value = str(severity_source).lower()
    for candidate in AlertSeverity:
        if candidate.value == severity_value:
            return candidate
    return AlertSeverity.LOW


# ── N3 — Router ─────────────────────────────────────────────────────────────


async def router_node(state: ProjectState) -> ProjectState:
    """N3 — Delegates doc-type classification to ClassifyDocumentUseCase."""
    if not _has_extractable_text(state.get("document_text")):
        state["doc_type"] = "insufficient_extractable_text"
        state["messages"].append(AIMessage(content=_insufficient_extractable_text_message()))
        return state
    if state.get("doc_type") in DOC_TYPES:
        return state
    use_case = ClassifyDocumentUseCase(ai=get_ai_service(state.get("tenant_id")))
    doc_type = await use_case.execute(
        ClassifyDocumentCommand(text=state["document_text"])
    )
    state["doc_type"] = doc_type
    state["messages"].append(AIMessage(content=f"Router doc_type={doc_type}"))
    return state


# ── N4 — Risk Extractor ─────────────────────────────────────────────────────


async def risk_extractor_node(state: ProjectState) -> ProjectState:
    """TS-QA-SWAGGER-ANALYSIS-001: extract risks via AI and fail honestly."""
    previous_confidence = state.get("confidence_score", 0.0)
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        _mark_risk_extraction_honest_failure(
            state,
            reason="AI risk extraction unavailable in mock mode — no risks extracted",
            previous_confidence=previous_confidence,
        )
        _append_risk_extraction_summary(state)
        return state

    from src.core.ai.tools import get_tool

    try:
        original_chars = len(state.get("document_text", "") or "")
        updated_state = await get_tool("risk_extraction", version="1.0")(state)
        risks = [
            _risk_contract_payload(item)
            for item in (updated_state.get("extracted_risks") or [])
        ]
        updated_state["extracted_risks"] = risks
    except Exception as exc:
        _mark_risk_extraction_honest_failure(
            state,
            reason="AI risk extraction failed/empty — no risks extracted",
            exc=exc,
            previous_confidence=previous_confidence,
        )
        _append_risk_extraction_summary(state)
        return state

    if not updated_state.get("extracted_risks"):
        _mark_risk_extraction_honest_failure(
            updated_state,
            reason="AI risk extraction failed/empty — no risks extracted",
            previous_confidence=previous_confidence,
        )
        updated_state["node_results"] = [
            *updated_state.get("node_results", []),
            _failed_node_result(
                "risk_extractor",
                RuntimeError("AI risk extraction returned no risk items"),
            ),
        ]
        _append_risk_extraction_summary(updated_state)
        return updated_state

    # Visibility marker so the /analyze response shows the filter ran.
    # The filter itself logs structured stats via the tool's logger.
    risks = updated_state.get("extracted_risks") or []
    updated_state["node_results"] = [
        *updated_state.get("node_results", []),
        _ok_node_result("risk_extractor", risks),
    ]
    updated_state["messages"].append(
        AIMessage(
            content=f"N4 risk_extractor: input_doc_chars={original_chars} "
            f"risks_emitted={len(updated_state.get('extracted_risks') or [])}"
        )
    )
    return updated_state


# ── N5 — WBS Extractor ──────────────────────────────────────────────────────


async def wbs_extractor_node(state: ProjectState) -> ProjectState:
    """N5 — Extract WBS items via WBSExtractionTool (AI) or deterministic rules (mock)."""
    if os.getenv("C2PRO_AI_MOCK", "0") == "1":
        wbs_items = [
            _wbs_contract_payload(item)
            for item in _wbs_rules.extract(state.get("document_text", ""))
        ]
        state["extracted_wbs"] = wbs_items
        state["node_results"] = [
            *state.get("node_results", []),
            _ok_node_result("wbs_extractor", wbs_items),
        ]
        state["messages"].append(
            AIMessage(content=f"WBS extractor mock mode: {len(state['extracted_wbs'])} items")
        )
        return state

    from src.core.ai.tools import get_tool

    try:
        updated_state = await get_tool("wbs_extraction", version="1.0")(state)
        wbs_items = [
            _wbs_contract_payload(item)
            for item in (updated_state.get("extracted_wbs") or [])
        ]
        updated_state["extracted_wbs"] = wbs_items
    except Exception as exc:
        node_result = _failed_node_result("wbs_extractor", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        state["extracted_wbs"] = []
        state["node_results"] = [*state.get("node_results", []), node_result]
        state["messages"].append(
            AIMessage(content="N5 wbs_extractor: failed (see node_results)")
        )
        return state

    wbs_items = updated_state.get("extracted_wbs") or []
    updated_state["node_results"] = [
        *updated_state.get("node_results", []),
        _ok_node_result("wbs_extractor", wbs_items),
    ]
    return updated_state


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
        state["node_results"] = [
            *state.get("node_results", []),
            _ok_node_result(
                "critique",
                {
                    "confidence": state["confidence_score"],
                    "retry_count": state["retry_count"],
                    "human_approval_required": state["human_approval_required"],
                },
                confidence=state["confidence_score"],
            ),
        ]
        state["messages"].append(AIMessage(content="Critique mock mode: passed."))
        return state

    use_case = CritiqueExtractionUseCase(ai=get_ai_service(state.get("tenant_id")))
    try:
        result = await use_case.execute(
            CritiqueExtractionCommand(
                extracted_risks=state["extracted_risks"],
                extracted_wbs=state["extracted_wbs"],
                doc_type=state.get("doc_type"),
                retry_count=state["retry_count"],
            )
        )
    except Exception as exc:
        node_result = _failed_node_result("critique", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        state["human_approval_required"] = True
        state["node_results"] = [*state.get("node_results", []), node_result]
        state["messages"].append(AIMessage(content="N12 critique: failed (see node_results)"))
        return state

    state["confidence_score"] = result.confidence
    state["retry_count"] = result.retry_count
    state["critique_notes"] = result.critique_notes
    state["human_approval_required"] = result.human_approval_required
    state["node_results"] = [
        *state.get("node_results", []),
        _ok_node_result(
            "critique",
            {
                "status": result.status,
                "confidence": result.confidence,
                "retry_count": result.retry_count,
                "human_approval_required": result.human_approval_required,
            },
            confidence=result.confidence,
        ),
    ]
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
    from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus

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
                metadata = {
                    "tenant_id": tenant_id,
                    "project_id": state["project_id"],
                    "document_id": state["document_id"],
                    "review_type": "analysis_critique",
                }
                if state.get("thread_id"):
                    metadata["thread_id"] = state["thread_id"]

                review_status = await service.route_for_review(
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
                        "thread_id": state.get("thread_id"),
                    },
                    metadata=metadata,
                )
                if review_status == ReviewStatus.APPROVED:
                    state["human_approval_required"] = False
                    state["messages"].append(
                        AIMessage(content="HITL auto-approved; continuing analysis.")
                    )
                    return state
        except Exception:
            import structlog

            state["node_results"] = [
                *state.get("node_results", []),
                NodeResult(
                    node="human_interrupt",
                    status=NodeStatus.DEGRADED,
                    degradation_reason="hitl_routing_failed",
                ),
            ]
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
    try:
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
    except Exception as exc:
        node_result = _failed_node_result("save_to_db", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        state["node_results"] = [*state.get("node_results", []), node_result]
        state["messages"].append(AIMessage(content="N17 save_to_db: failed (see node_results)"))
        return state

    state["analysis_id"] = str(result.analysis_id)
    state["node_results"] = [
        *state.get("node_results", []),
        _ok_node_result("save_to_db", {"analysis_id": str(result.analysis_id)}),
    ]
    state["messages"].append(AIMessage(content=f"Persisted analysis {result.analysis_id}."))
    return state
