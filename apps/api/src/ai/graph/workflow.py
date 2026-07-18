"""Re-export workflow from analysis.adapters.graph.

This module provides a compile_workflow that builds a simplified
extraction-critique-save graph using module-level node references
so that monkeypatching works in tests.
"""

import sys
from typing import Any, Literal

from langgraph.graph import END, StateGraph

# Re-imported AFTER the star import so the legacy facade's critique_node
# (which resolves _critique_extraction via sys.modules at call time and
# therefore supports monkeypatching) is the one bound on this module.
from src.ai.graph.nodes import (
    budget_parser_node,  # noqa: F401
    critique_node,  # noqa: F401
    human_interrupt_node,  # noqa: F401
    risk_extractor_node,  # noqa: F401
    router_node,  # noqa: F401
    save_to_db_node,  # noqa: F401
    wbs_extractor_node,  # noqa: F401
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.adapters.graph.workflow import (
    _persist_graph_diagram,
    build_workflow,  # noqa: F401
    close_checkpointer_resources,  # noqa: F401
    ensure_checkpointer_ready,  # noqa: F401
    get_graph_app,  # noqa: F401
    run_orchestration,  # noqa: F401
)


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


def compile_workflow(checkpointer: Any = None, persist_diagram: bool = True) -> Any:
    """Build and compile a simplified extraction workflow.

    This builds a smaller graph (router → extractor → critique → save)
    using this module's node references so monkeypatching works in tests.
    """
    _this = sys.modules[__name__]

    workflow = StateGraph(ProjectState)

    # Register nodes from this module's namespace (supports monkeypatching)
    workflow.add_node("router", _this.router_node)
    workflow.add_node("risk_extractor", _this.risk_extractor_node)
    workflow.add_node("wbs_extractor", _this.wbs_extractor_node)
    workflow.add_node("budget_parser", _this.budget_parser_node)
    workflow.add_node("critique", _this.critique_node)
    workflow.add_node("human_interrupt", _this.human_interrupt_node)
    workflow.add_node("save_to_db", _this.save_to_db_node)

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
