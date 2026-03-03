"""Re-export workflow from analysis.adapters.graph.

This module provides a compile_workflow that builds a simplified
extraction-critique-save graph using module-level node references
so that monkeypatching works in tests.
"""

import sys
from typing import Literal

from src.analysis.adapters.graph.workflow import *  # noqa: F401, F403
from src.analysis.adapters.graph.workflow import (
    compile_workflow as _original_compile_workflow,
    _persist_graph_diagram,
)
from src.analysis.adapters.graph.nodes import (
    budget_parser_node,
    human_interrupt_node,
    risk_extractor_node,
    router_node,
    save_to_db_node,
    wbs_extractor_node,
)
from src.ai.graph.nodes import critique_node  # noqa: F401 - uses module-level _critique_extraction
from src.analysis.adapters.graph.schema import ProjectState
from langgraph.graph import END, StateGraph


def _next_after_critique(state: ProjectState) -> Literal[
    "risk_extractor",
    "wbs_extractor",
    "budget_parser",
    "human_interrupt",
    "save_to_db",
]:
    """Critique router for the simplified extraction graph."""
    if state.get("human_approval_required"):
        return "human_interrupt"
    if state.get("critique_notes") and state.get("retry_count", 0) > 0:
        retry_count = state["retry_count"]
        if retry_count <= 2:
            if state.get("doc_type") == "contract":
                return "risk_extractor"
            if state.get("doc_type") == "budget":
                return "budget_parser"
            return "wbs_extractor"
    return "save_to_db"


def compile_workflow(checkpointer=None, persist_diagram: bool = True):
    """Build and compile a simplified extraction workflow.

    This builds a smaller graph (router → extractor → critique → save)
    using this module's node references so monkeypatching works in tests.
    """
    _this = sys.modules[__name__]

    workflow = StateGraph(ProjectState)

    # Register nodes from this module's namespace (supports monkeypatching)
    workflow.add_node("router", getattr(_this, "router_node"))
    workflow.add_node("risk_extractor", getattr(_this, "risk_extractor_node"))
    workflow.add_node("wbs_extractor", getattr(_this, "wbs_extractor_node"))
    workflow.add_node("budget_parser", getattr(_this, "budget_parser_node"))
    workflow.add_node("critique", getattr(_this, "critique_node"))
    workflow.add_node("human_interrupt", getattr(_this, "human_interrupt_node"))
    workflow.add_node("save_to_db", getattr(_this, "save_to_db_node"))

    # Entry point
    workflow.set_entry_point("router")

    # Router → extraction branch
    workflow.add_conditional_edges(
        "router",
        lambda state: state["doc_type"],
        {"contract": "risk_extractor", "technical_spec": "wbs_extractor", "budget": "budget_parser"},
    )

    # Extractors → critique
    workflow.add_edge("risk_extractor", "critique")
    workflow.add_edge("wbs_extractor", "critique")
    workflow.add_edge("budget_parser", "critique")

    # Critique → retry, HITL, or save
    workflow.add_conditional_edges(
        "critique",
        _next_after_critique,
        {
            "risk_extractor": "risk_extractor",
            "wbs_extractor": "wbs_extractor",
            "budget_parser": "budget_parser",
            "human_interrupt": "human_interrupt",
            "save_to_db": "save_to_db",
        },
    )

    workflow.add_edge("human_interrupt", "save_to_db")
    workflow.add_edge("save_to_db", END)

    app = workflow.compile(checkpointer=checkpointer)
    if persist_diagram:
        _persist_graph_diagram(app)
    return app


__all__ = ["compile_workflow"]
