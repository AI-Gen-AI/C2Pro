from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.ai.graph.nodes import (
    human_interrupt_node,
    quality_check_node,
    risk_extractor_node,
    router_node,
    save_to_db_node,
    wbs_extractor_node,
)
from src.ai.graph.state import AgentState

_graph_app = None


def _build_workflow() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("risk_extractor", risk_extractor_node)
    workflow.add_node("wbs_extractor", wbs_extractor_node)
    workflow.add_node("quality_check", quality_check_node)
    workflow.add_node("human_interrupt", human_interrupt_node)
    workflow.add_node("save_to_db", save_to_db_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        lambda state: state["next_step"],
        {
            "risk_extractor": "risk_extractor",
            "wbs_extractor": "wbs_extractor",
        },
    )

    workflow.add_edge("risk_extractor", "quality_check")
    workflow.add_edge("wbs_extractor", "quality_check")

    workflow.add_conditional_edges(
        "quality_check",
        lambda state: "human_interrupt" if state["human_approval_required"] else "save_to_db",
        {
            "human_interrupt": "human_interrupt",
            "save_to_db": "save_to_db",
        },
    )

    workflow.add_edge("human_interrupt", "save_to_db")
    workflow.add_edge("save_to_db", END)

    return workflow


def get_graph_app():
    global _graph_app
    if _graph_app is not None:
        return _graph_app

    from langgraph.checkpoint.memory import MemorySaver

    workflow = _build_workflow()
    _graph_app = workflow.compile(checkpointer=MemorySaver())
    return _graph_app
