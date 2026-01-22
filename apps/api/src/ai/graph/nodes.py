from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage

from src.ai.agents.risk_agent import RiskExtractionAgent
from src.ai.agents.wbs_agent import WBSExtractionAgent
from src.ai.graph.state import AgentState
from src.core.database import get_session_with_tenant
from src.modules.analysis.models import Alert, AlertSeverity, Analysis, AnalysisStatus, AnalysisType
from src.modules.stakeholders.models import WBSItem, WBSItemType

def _average_confidence(items: list[dict[str, Any]]) -> float:
    confidences = [item.get("confidence") for item in items if isinstance(item.get("confidence"), (int, float))]
    if not confidences:
        return 0.0 if not items else 0.9
    return float(sum(confidences)) / float(len(confidences))


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _is_contract_document(text: str) -> bool:
    normalized = text.lower()
    keywords = ("contrato", "clausula", "adenda", "partes", "obligaciones")
    return any(keyword in normalized for keyword in keywords)


async def router_node(state: AgentState) -> AgentState:
    next_step = "risk_extractor" if _is_contract_document(state["document_text"]) else "wbs_extractor"
    state["next_step"] = next_step
    state["messages"].append(AIMessage(content=f"Router selected: {next_step}"))
    return state


async def risk_extractor_node(state: AgentState) -> AgentState:
    agent = RiskExtractionAgent(tenant_id=state["tenant_id"])
    state["risks"] = await agent.extract(state["document_text"])
    state["messages"].append(AIMessage(content=f"Risk extraction produced {len(state['risks'])} items."))
    return state


async def wbs_extractor_node(state: AgentState) -> AgentState:
    agent = WBSExtractionAgent(tenant_id=state["tenant_id"])
    state["wbs"] = await agent.extract(state["document_text"])
    state["messages"].append(AIMessage(content=f"WBS extraction produced {len(state['wbs'])} items."))
    return state


async def quality_check_node(state: AgentState) -> AgentState:
    items = state["risks"] if state["risks"] else state["wbs"]
    confidence = _average_confidence(items)
    state["human_approval_required"] = confidence < 0.8
    state["messages"].append(
        AIMessage(content=f"Quality check confidence={confidence:.2f}, approval_required={state['human_approval_required']}.")
    )
    return state


async def human_interrupt_node(state: AgentState) -> AgentState:
    from langgraph.types import interrupt

    interrupt(
        {
            "reason": "low_confidence",
            "project_id": state["project_id"],
            "next_step": state["next_step"],
        }
    )
    state["messages"].append(AIMessage(content="Human approval requested."))
    return state


async def save_to_db_node(state: AgentState) -> AgentState:
    if not state.get("tenant_id"):
        state["messages"].append(AIMessage(content="Missing tenant_id; skipping persistence."))
        return state

    project_id = UUID(state["project_id"])
    tenant_id = UUID(state["tenant_id"])
    analysis_type = AnalysisType.RISK if state["risks"] else AnalysisType.SCHEDULE

    async with get_session_with_tenant(tenant_id) as session:
        analysis = Analysis(
            project_id=project_id,
            analysis_type=analysis_type,
            status=AnalysisStatus.COMPLETED,
            result_json={"risks": state["risks"], "wbs": state["wbs"]},
        )
        session.add(analysis)
        await session.flush()

        if state["risks"]:
            alerts = []
            for item in state["risks"]:
                severity_value = str(item.get("severity", "low")).lower()
                severity = AlertSeverity.LOW
                for candidate in AlertSeverity:
                    if candidate.value == severity_value:
                        severity = candidate
                        break

                alerts.append(
                    Alert(
                        project_id=project_id,
                        analysis_id=analysis.id,
                        severity=severity,
                        title=item.get("title") or "Risk identified",
                        description=item.get("description") or "Risk detected by AI extraction.",
                        category="risk",
                        impact_level=item.get("impact_level"),
                        alert_metadata={"confidence": item.get("confidence"), "raw": item},
                    )
                )
            session.add_all(alerts)

        if state["wbs"]:
            wbs_items = []
            for item in state["wbs"]:
                code = str(item.get("code") or "").strip() or f"T{len(wbs_items) + 1}"
                level = code.count(".") + 1 if code else 1
                item_type_raw = str(item.get("item_type") or "").lower()
                item_type = None
                for candidate in WBSItemType:
                    if candidate.value == item_type_raw:
                        item_type = candidate
                        break

                wbs_items.append(
                    WBSItem(
                        project_id=project_id,
                        wbs_code=code,
                        name=item.get("name") or "WBS Item",
                        description=item.get("description"),
                        level=level,
                        item_type=item_type,
                        wbs_metadata={"confidence": item.get("confidence"), "raw": item},
                        budget_allocated=_parse_decimal(item.get("budget_allocated")),
                    )
                )
            session.add_all(wbs_items)

        state["analysis_id"] = str(analysis.id)
        state["messages"].append(
            AIMessage(content=f"Persisted analysis {analysis.id} (type={analysis_type.value}).")
        )
    return state
