from __future__ import annotations

from pathlib import Path

import structlog
from langgraph.graph import END, StateGraph

from src.analysis.adapters.graph.nodes import (
    budget_parser_node,
    critique_node,
    human_interrupt_node,
    risk_extractor_node,
    router_node,
    save_to_db_node,
    wbs_extractor_node,
    _next_after_critique,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.config import settings

logger = structlog.get_logger()

_graph_app = None


def build_workflow() -> StateGraph:
    workflow = StateGraph(ProjectState)

    workflow.add_node("router", router_node)
    workflow.add_node("risk_extractor", risk_extractor_node)
    workflow.add_node("wbs_extractor", wbs_extractor_node)
    workflow.add_node("budget_parser", budget_parser_node)
    workflow.add_node("critique", critique_node)
    workflow.add_node("human_interrupt", human_interrupt_node)
    workflow.add_node("save_to_db", save_to_db_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        lambda state: state["doc_type"],
        {
            "contract": "risk_extractor",
            "technical_spec": "wbs_extractor",
            "budget": "budget_parser",
        },
    )

    workflow.add_edge("risk_extractor", "critique")
    workflow.add_edge("wbs_extractor", "critique")
    workflow.add_edge("budget_parser", "critique")

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

    return workflow


def _build_checkpointer():
    if settings.database_url_async.startswith("sqlite"):
        raise RuntimeError("Postgres checkpointer requires a PostgreSQL database URL.")

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError:
        from langgraph.checkpoint.postgres import AsyncPostgresSaver

    return AsyncPostgresSaver.from_conn_string(
        settings.database_url_async,
        table_name="ai_checkpoints",
    )


def _persist_graph_diagram(app) -> None:
    try:
        png_bytes = app.get_graph().draw_png()
    except Exception:
        logger.warning("langgraph_diagram_failed", exc_info=True)
        return

    output_dir = Path(settings.local_storage_path) / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "langgraph.png"
    output_path.write_bytes(png_bytes)
    logger.info("langgraph_diagram_written", path=str(output_path))


def compile_workflow(checkpointer=None, persist_diagram: bool = True):
    workflow = build_workflow()
    app = workflow.compile(checkpointer=checkpointer)
    if persist_diagram:
        _persist_graph_diagram(app)
    return app


def get_graph_app():
    global _graph_app
    if _graph_app is not None:
        return _graph_app

    _graph_app = compile_workflow(checkpointer=_build_checkpointer())
    return _graph_app
