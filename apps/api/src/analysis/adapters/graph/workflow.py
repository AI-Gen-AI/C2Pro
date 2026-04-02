from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

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
)
from src.analysis.adapters.graph.nodes_extended import (
    citation_validator_node,
    coherence_scorer_node,
    decision_intelligence_node,
    document_ingestion_node,
    final_assembler_node,
    knowledge_graph_builder_node,
    pii_anonymizer_node,
    raci_generator_node,
    stakeholder_extractor_node,
)
from src.analysis.adapters.graph.schema import ProjectState

logger = structlog.get_logger()

_graph_app = None


# ── Conditional edge: route after critique ──────────────────────────────────

def _next_after_critique_v2(state: ProjectState) -> Literal[
    "risk_extractor",
    "wbs_extractor",
    "budget_parser",
    "human_interrupt",
    "stakeholder_extractor",
]:
    """Extended critique router — sends to N13/14 (HITL) or enrichment nodes."""
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
    # Critique passed — proceed to enrichment pipeline
    return "stakeholder_extractor"


# ── Graph builder ────────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    """Build the full N1–N17 orchestration graph.

    Graph topology::

        N1 (document_ingestion)
         │
        N2 (pii_anonymizer)
         │
        N3 (router) ──► [N4 risk | N5 wbs | N9 budget]
                              │
                         N12 (critique)
                              │
              ┌───────────────┼──────────────┐
              ▼               ▼              ▼
         (retry N4/5/9)   N13/14 (HITL)   N6 (stakeholder_extractor)
                              │              │
                              ▼              ▼
                         N6 (stakeholder)  N7 (raci_generator)
                                             │
                                            N8 (coherence_scorer)
                                             │
                                           N15 (citation_validator)
                                             │
                                           N10 (knowledge_graph)
                                             │
                                           N17 (save_to_db)
                                             │
                                           N11 (decision_intelligence)
                                             │
                                           N16 (final_assembler)
                                             │
                                            END
    """
    workflow = StateGraph(ProjectState)

    # ── Register all 17 nodes ──
    # Pre-processing
    workflow.add_node("document_ingestion", document_ingestion_node)    # N1
    workflow.add_node("pii_anonymizer", pii_anonymizer_node)           # N2

    # Classification & extraction
    workflow.add_node("router", router_node)                            # N3
    workflow.add_node("risk_extractor", risk_extractor_node)            # N4
    workflow.add_node("wbs_extractor", wbs_extractor_node)              # N5
    workflow.add_node("budget_parser", budget_parser_node)              # N9

    # QA & HITL
    workflow.add_node("critique", critique_node)                        # N12
    workflow.add_node("human_interrupt", human_interrupt_node)          # N13/N14

    # Enrichment
    workflow.add_node("stakeholder_extractor", stakeholder_extractor_node)  # N6
    workflow.add_node("raci_generator", raci_generator_node)                # N7
    workflow.add_node("coherence_scorer", coherence_scorer_node)            # N8

    # Validation & persistence
    workflow.add_node("citation_validator", citation_validator_node)    # N15
    workflow.add_node("knowledge_graph", knowledge_graph_builder_node)  # N10
    workflow.add_node("save_to_db", save_to_db_node)                   # N17

    # Assembly
    workflow.add_node("decision_intelligence", decision_intelligence_node)  # N11
    workflow.add_node("final_assembler", final_assembler_node)              # N16

    # ── Entry point ──
    workflow.set_entry_point("document_ingestion")

    # ── Pre-processing chain: N1 → N2 → N3 ──
    workflow.add_edge("document_ingestion", "pii_anonymizer")
    workflow.add_edge("pii_anonymizer", "router")

    # ── Router (N3) → extraction branch ──
    workflow.add_conditional_edges(
        "router",
        lambda state: state["doc_type"],
        {
            "contract": "risk_extractor",
            "technical_spec": "wbs_extractor",
            "budget": "budget_parser",
        },
    )

    # ── Extraction → Critique ──
    workflow.add_edge("risk_extractor", "critique")
    workflow.add_edge("wbs_extractor", "critique")
    workflow.add_edge("budget_parser", "critique")

    # ── Critique (N12) → retry / HITL / enrichment ──
    workflow.add_conditional_edges(
        "critique",
        _next_after_critique_v2,
        {
            "risk_extractor": "risk_extractor",
            "wbs_extractor": "wbs_extractor",
            "budget_parser": "budget_parser",
            "human_interrupt": "human_interrupt",
            "stakeholder_extractor": "stakeholder_extractor",
        },
    )

    # ── HITL (N13/14) → enrichment ──
    workflow.add_edge("human_interrupt", "stakeholder_extractor")

    # ── Enrichment chain: N6 → N7 → N8 ──
    workflow.add_edge("stakeholder_extractor", "raci_generator")
    workflow.add_edge("raci_generator", "coherence_scorer")

    # ── Validation & persistence: N8 → N15 → N10 → N17 ──
    workflow.add_edge("coherence_scorer", "citation_validator")
    workflow.add_edge("citation_validator", "knowledge_graph")
    workflow.add_edge("knowledge_graph", "save_to_db")

    # ── Assembly: N17 → N11 → N16 → END ──
    workflow.add_edge("save_to_db", "decision_intelligence")
    workflow.add_edge("decision_intelligence", "final_assembler")
    workflow.add_edge("final_assembler", END)

    return workflow


# ── Infrastructure helpers (unchanged) ───────────────────────────────────────

_checkpointer_pool = None
_checkpointer_ready = False
_checkpointer_setup_lock = asyncio.Lock()

def _build_checkpointer():
    """
    Build a checkpointer for persistent state management.

    For PostgreSQL, uses AsyncPostgresSaver with connection pool.
    Falls back to MemorySaver for SQLite or if postgres package not installed.

    Note: The pool is created with min_size=0, max_size=10 to avoid blocking on sync initialization.
    The pool will automatically open connections as needed.
    """
    from src.config import settings

    if settings.database_url_async.startswith("sqlite"):
        logger.warning("checkpointer_fallback", reason="SQLite not supported for postgres checkpointer")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    try:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError:
            from langgraph.checkpoint.postgres import AsyncPostgresSaver

        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        global _checkpointer_pool
        if _checkpointer_pool is None:
            conn_string = settings.database_url_async.replace("postgresql+asyncpg://", "postgresql://")

            _checkpointer_pool = AsyncConnectionPool(
                conninfo=conn_string,
                min_size=0,
                max_size=10,
                open=False,
                kwargs={
                    "autocommit": True,
                    # Disable prepared statements entirely for PgBouncer/Railway pooler compatibility.
                    "prepare_threshold": None,
                    "row_factory": dict_row,
                },
            )

        return AsyncPostgresSaver(conn=_checkpointer_pool)
    except ImportError as e:
        logger.warning(
            "checkpointer_fallback",
            reason=f"langgraph-checkpoint-postgres dependencies not installed: {e}, using MemorySaver",
        )
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


async def ensure_checkpointer_ready() -> None:
    """Ensure PostgreSQL checkpointer tables/migrations are initialized exactly once."""
    global _checkpointer_ready

    if _checkpointer_ready:
        return

    app = get_graph_app()
    checkpointer = getattr(app, "checkpointer", None)
    if checkpointer is None:
        return

    setup = getattr(checkpointer, "setup", None)
    if not callable(setup):
        _checkpointer_ready = True
        return

    async with _checkpointer_setup_lock:
        if _checkpointer_ready:
            return
        if _checkpointer_pool is not None and getattr(_checkpointer_pool, "closed", False):
            await _checkpointer_pool.open()
        setup_result = setup()
        if asyncio.iscoroutine(setup_result):
            await setup_result
        _checkpointer_ready = True
        logger.info("langgraph_checkpointer_ready", checkpointer_type=type(checkpointer).__name__)


async def close_checkpointer_resources() -> None:
    """Close pooled DB resources used by the checkpointer on app shutdown."""
    global _checkpointer_pool, _checkpointer_ready, _graph_app

    if _checkpointer_pool is None:
        _graph_app = None
        return

    await _checkpointer_pool.close()
    _checkpointer_pool = None
    _checkpointer_ready = False
    _graph_app = None


def _persist_graph_diagram(app) -> None:
    from src.config import settings

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

    # Disable diagram persistence to avoid pygraphviz dependency
    _graph_app = compile_workflow(checkpointer=_build_checkpointer(), persist_diagram=False)
    return _graph_app


async def run_orchestration(initial_state: dict, thread_id: str) -> dict:
    """
    Run the LangGraph orchestration workflow with the given initial state.

    Args:
        initial_state: Dictionary containing the initial state for the workflow
        thread_id: Unique identifier for this thread (used for checkpointing)

    Returns:
        Dictionary containing the final state after workflow execution

    Note:
        Traces are automatically sent to LangSmith when LANGCHAIN_TRACING_V2=true
    """
    await ensure_checkpointer_ready()
    app = get_graph_app()

    # Build run name from state for better LangSmith trace identification
    project_id = initial_state.get("project_id", "unknown")
    doc_type = initial_state.get("doc_type", "document")
    run_name = f"C2Pro_Orchestration_{doc_type}_{project_id[:8] if project_id != 'unknown' else 'new'}"

    # Configure the thread for checkpointing + LangSmith tracing
    config = {
        "configurable": {
            "thread_id": thread_id
        },
        "run_name": run_name,
        "tags": ["c2pro", "orchestration", doc_type],
        "metadata": {
            "project_id": project_id,
            "thread_id": thread_id,
        },
    }

    # Invoke the graph with the initial state
    result = await app.ainvoke(initial_state, config)

    logger.info(
        "orchestration_completed",
        thread_id=thread_id,
        project_id=result.get("project_id"),
        doc_type=result.get("doc_type"),
        human_approval_required=result.get("human_approval_required", False),
    )

    return result
