from __future__ import annotations

import asyncio
import os
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph._node import StateNode
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

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
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService

if TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger()

ProjectWorkflow = StateGraph[ProjectState, None, ProjectState, ProjectState]
ProjectGraph = CompiledStateGraph[ProjectState, None, ProjectState, ProjectState]


class AsyncPostgresSaverFactory(Protocol):
    """Factory protocol shared by the legacy and current checkpoint imports."""

    def __call__(
        self,
        *,
        conn: AsyncConnectionPool[AsyncConnection[dict[str, Any]]],
    ) -> BaseCheckpointSaver[str]: ...


_graph_app: ProjectGraph | None = None

# Stateless routing service — reused across all conditional-edge evaluations.
_critique_evaluator = CritiqueEvaluationService()


# ── Conditional edge: route after critique ──────────────────────────────────
#
# Returns the *logical* routing decision string. The physical destination may
# be remapped in the conditional path_map (see ``build_workflow``):
# ``"stakeholder_extractor"`` is remapped to ``"enrichment_dispatch"``, the
# fan-out node that launches the parallel enrichment branches. The Literal
# return type is preserved verbatim so unit tests in
# ``tests/analysis/adapters/graph/test_workflow_routing_swarm.py`` (which
# assert these exact strings) keep working unchanged.

def _next_after_critique_v2(state: ProjectState) -> Literal[
    "risk_extractor",
    "wbs_extractor",
    "budget_parser",
    "human_interrupt",
    "stakeholder_extractor",
]:
    """Thin conditional edge — delegates branching to CritiqueEvaluationService.

    Two escape hatches let operators force the flow past the HITL gate so
    that downstream nodes (N8 coherence_scorer with the risk→signal bridge,
    N17 save_to_db) actually run even when the LLM extraction quality is
    low and critique would normally pause for human review:

    * ``C2PRO_AI_MOCK=1`` — historical mock-mode flag (kept for tests).
    * ``C2PRO_SKIP_HITL=1`` — independent operator override. Lets you
      use a real LLM but skip the HITL pause so coherence/persistence
      still complete. ``human_approval_required`` remains in state for
      visibility, but the workflow routes through enrichment_dispatch.
    """
    return cast(
        Literal[
            "risk_extractor",
            "wbs_extractor",
            "budget_parser",
            "human_interrupt",
            "stakeholder_extractor",
        ],
        _critique_evaluator.determine_next_step(
            human_approval_required=bool(state.get("human_approval_required")),
            critique_notes=state.get("critique_notes", "") or "",
            retry_count=int(state.get("retry_count", 0)),
            doc_type=state.get("doc_type") or "",
            skip_hitl=(
                os.getenv("C2PRO_SKIP_HITL", "0") == "1"
                or os.getenv("C2PRO_AI_MOCK", "0") == "1"
            ),
        ),
    )


# ── Enrichment fan-out point (passthrough) ──────────────────────────────────


async def enrichment_dispatch_node(_state: ProjectState) -> dict[str, Any]:
    """TS-UA-ANA-GRAPH-001 - Anchor the fan-out without rewriting shared state.

    Why this node exists:
        1. The critique conditional edge must terminate at a *single* physical
           target (LangGraph conditional ``path_map`` values are 1:1, not 1:N).
           Routing the logical decision ``"stakeholder_extractor"`` to this
           dispatch keeps the routing service contract unchanged.
        2. ``human_interrupt`` (N13/14) rejoins the same dispatch so both the
           HITL and non-HITL paths feed a unified parallel cut.
        3. With three unconditional outgoing edges, LangGraph launches N6, N8,
           and N15 concurrently — this is the canonical static-parallelism
           idiom and avoids the ``Send`` API (which would fork state in ways
           that complicate the N10 fan-in merge).

    State semantics:
        Emits an empty patch. The incoming state already exists in the graph;
        rewriting the full state immediately before a parallel cut can cause
        identity keys such as ``project_id`` to be observed as concurrent
        writes by LangGraph.
    """
    return {}


# ── Graph builder ────────────────────────────────────────────────────────────


def build_workflow() -> ProjectWorkflow:
    """Build the full N1–N17 orchestration graph with parallel enrichment.

    Topology::

        N1 (document_ingestion)
         │
        N2 (pii_anonymizer)
         │
        N3 (router) ──► [N4 risk | N5 wbs | N9 budget]
                              │
                         N12 (critique)
                              │
              ┌───────────────┼─────────────────────────┐
              ▼               ▼                         ▼
         (retry N4/5/9)  N13/14 (HITL)         enrichment_dispatch
                              │                         ▲
                              └─────────────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────────┐
                              ▼                         ▼                         ▼
                       N6 (stakeholder)         N8 (coherence)           N15 (citation)
                              │
                       N7 (raci)
                              │                         │                         │
                              └────────────► N10 (knowledge_graph) ◄──────────────┘
                                                        │   (fan-in barrier)
                                                  N17 (save_to_db)
                                                        │
                                              N11 (decision_intelligence)
                                                        │
                                                  N16 (final_assembler)
                                                        │
                                                       END

    Parallel-write state-safety contract (see ``ProjectState``):

        Branch A:  N6 → ``extracted_stakeholders``
                   N7 → ``raci_matrix``
        Branch B:  N8 → ``coherence_score``, ``coherence_breakdown``,
                        ``coherence_reason``, ``coherence_missing_dimensions``
        Branch C:  N15 → ``citations``, ``citation_validation_passed``

        Every branch writes a *disjoint* set of state keys, so LangGraph's
        default last-write-wins merge is correct for them — **no additional
        reducers required**. The only shared key is ``messages``, whose
        schema already declares ``Annotated[list[BaseMessage], add_messages]``.
        ``add_messages`` performs id-based deduplicated append, which is
        exactly the merge semantic needed at the N10 fan-in barrier.

    Routing contract preserved:

        ``CritiqueEvaluationService.determine_next_step`` still returns the
        literal string ``"stakeholder_extractor"`` (asserted by
        ``test_workflow_routing_swarm.py``). The conditional ``path_map``
        below remaps that *logical* destination to the *physical* dispatch
        node. Tests are not affected.
    """
    workflow: ProjectWorkflow = StateGraph(ProjectState)

    # ── Node registration ────────────────────────────────────────────────
    # Pre-processing
    workflow.add_node("document_ingestion", document_ingestion_node)        # N1
    workflow.add_node("pii_anonymizer", pii_anonymizer_node)                # N2

    # Classification & extraction
    workflow.add_node("router", router_node)                                # N3
    workflow.add_node("risk_extractor", risk_extractor_node)                # N4
    workflow.add_node("wbs_extractor", wbs_extractor_node)                  # N5
    workflow.add_node("budget_parser", budget_parser_node)                  # N9

    # QA & HITL
    workflow.add_node("critique", critique_node)                            # N12
    workflow.add_node("human_interrupt", human_interrupt_node)              # N13/N14

    # Parallel-enrichment fan-out point (passthrough — no business logic)
    workflow.add_node(
        "enrichment_dispatch",
        cast(StateNode[ProjectState, None], enrichment_dispatch_node),
    )

    # Enrichment branches (run concurrently after dispatch)
    workflow.add_node("stakeholder_extractor", stakeholder_extractor_node)  # N6
    workflow.add_node("raci_generator", raci_generator_node)                # N7
    workflow.add_node("coherence_scorer", coherence_scorer_node)            # N8
    workflow.add_node("citation_validator", citation_validator_node)        # N15

    # Synthesis & persistence
    workflow.add_node("knowledge_graph", knowledge_graph_builder_node)      # N10 (fan-in)
    workflow.add_node("save_to_db", save_to_db_node)                        # N17

    # Assembly
    workflow.add_node("decision_intelligence", decision_intelligence_node)  # N11
    workflow.add_node("final_assembler", final_assembler_node)              # N16

    # ── Entry ────────────────────────────────────────────────────────────
    workflow.set_entry_point("document_ingestion")

    # ── Pre-processing chain: N1 → N2 → N3 ──────────────────────────────
    workflow.add_edge("document_ingestion", "pii_anonymizer")
    workflow.add_edge("pii_anonymizer", "router")

    # ── Router (N3) → extraction branch ─────────────────────────────────
    workflow.add_conditional_edges(
        "router",
        lambda state: state["doc_type"],
        {
            "contract": "risk_extractor",
            "technical_spec": "wbs_extractor",
            "budget": "budget_parser",
            "schedule": "wbs_extractor",
            "specification": "wbs_extractor",
            "drawing": "wbs_extractor",
            "other": "risk_extractor",
        },
    )

    # ── Extraction → Critique (N12) ─────────────────────────────────────
    workflow.add_edge("risk_extractor", "critique")
    workflow.add_edge("wbs_extractor", "critique")
    workflow.add_edge("budget_parser", "critique")

    # ── Critique (N12) → retry / HITL / parallel-enrichment dispatch ────
    # Path-map keys are the logical strings returned by
    # CritiqueEvaluationService.determine_next_step. The decision
    # "stakeholder_extractor" is *physically* routed to "enrichment_dispatch"
    # so that the fan-out point is centralized.
    workflow.add_conditional_edges(
        "critique",
        _next_after_critique_v2,
        {
            "risk_extractor": "risk_extractor",
            "wbs_extractor": "wbs_extractor",
            "budget_parser": "budget_parser",
            "human_interrupt": "human_interrupt",
            "stakeholder_extractor": "enrichment_dispatch",  # logical → physical
        },
    )

    # ── HITL exit converges on the same dispatch node ───────────────────
    # (Mutually exclusive with the direct critique→dispatch path; only one
    # of these two edges fires per execution, so this is *not* a join.)
    workflow.add_edge("human_interrupt", "enrichment_dispatch")

    # ── Parallel fan-out from dispatch ──────────────────────────────────
    # Multiple unconditional outgoing edges from a single node = static
    # parallel dispatch in LangGraph. All three branches receive the same
    # input state and execute concurrently. The state-safety contract above
    # guarantees that branch writes are disjoint (except ``messages``, which
    # is reduced by ``add_messages``).
    workflow.add_edge("enrichment_dispatch", "stakeholder_extractor")  # branch A start
    workflow.add_edge("enrichment_dispatch", "coherence_scorer")       # branch B
    workflow.add_edge("enrichment_dispatch", "citation_validator")     # branch C

    # Branch A is internally sequential because N7 strictly depends on
    # ``extracted_stakeholders`` produced by N6.
    workflow.add_edge("stakeholder_extractor", "raci_generator")       # N6 → N7

    # ── Fan-in barrier at N10 (knowledge_graph) ─────────────────────────
    # A list-valued start edge is LangGraph's true "wait for all" join.
    # Three separate edges would let N10 fire independently as each branch
    # completes, duplicating downstream writes such as project_id/analysis_id.
    workflow.add_edge(
        ["raci_generator", "coherence_scorer", "citation_validator"],
        "knowledge_graph",
    )

    # ── Persistence & assembly: N10 → N17 → N11 → N16 → END ─────────────
    workflow.add_edge("knowledge_graph", "save_to_db")
    workflow.add_edge("save_to_db", "decision_intelligence")
    workflow.add_edge("decision_intelligence", "final_assembler")
    workflow.add_edge("final_assembler", END)

    return workflow


# ── Infrastructure helpers ───────────────────────────────────────────────────
#
# Option-C C2 (checkpoint role boundary): runtime no longer calls
# AsyncPostgresSaver.setup() -- that DDL now runs exclusively from
# scripts/checkpoint_bootstrap.py under the owner/admin credential
# (c2pro_owner). setup() unconditionally re-issues
# `CREATE TABLE IF NOT EXISTS checkpoint_migrations` on every call regardless
# of migration state (proven by the C2 investigation, apps/api/scripts/
# c2_checkpoint_investigation.py), which requires schema CREATE privilege
# even against an already-current schema -- a restricted, non-owning
# `c2pro_checkpoint` runtime role can never satisfy that. Runtime now performs
# a read-only readiness check instead (see verify_checkpoint_schema_ready
# below), which needs no privilege beyond SELECT on the checkpoint tables
# themselves and a read of information_schema (universally readable -- no
# GRANT needed, and no access to checkpoint_migrations required either).

_checkpointer_pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] | None = None
_checkpointer_ready = False
_checkpointer_setup_lock = asyncio.Lock()

# The newest of AsyncPostgresSaver's 10 built-in migrations (v0-v9, as pinned
# by langgraph-checkpoint-postgres==3.1.2) adds this column. Its presence is
# a reliable, read-only proxy for "the checkpoint schema is fully current" --
# checking it needs only SELECT on information_schema, which every role can
# always read regardless of table-level GRANTs.
_CHECKPOINT_SCHEMA_MARKER_TABLE = "checkpoint_writes"
_CHECKPOINT_SCHEMA_MARKER_COLUMN = "task_path"


class CheckpointSchemaNotReadyError(RuntimeError):
    """Raised when the checkpoint schema is missing or not fully migrated.

    This must propagate out of ensure_checkpointer_ready() rather than being
    caught and downgraded to a warning: a missing/outdated checkpoint schema
    is a deployment problem (the owner bootstrap step -- scripts/
    checkpoint_bootstrap.py -- was not run, or LangGraph's checkpoint-postgres
    package was upgraded without re-running it) and must be an observable
    startup failure, not a silently degraded runtime state.
    """


def _async_postgres_saver_factory() -> AsyncPostgresSaverFactory:
    """Load the saver across the two supported LangGraph module layouts."""
    try:
        module = import_module("langgraph.checkpoint.postgres.aio")
    except ImportError:
        module = import_module("langgraph.checkpoint.postgres")
    return cast(AsyncPostgresSaverFactory, module.AsyncPostgresSaver)


def _checkpoint_pool_conninfo() -> str:
    """Resolve and log the checkpoint runtime DSN (never silently falls back)."""
    from src.config import settings

    if settings.checkpoint_database_url_is_fallback:
        logger.warning(
            "checkpoint_dsn_fallback",
            reason=(
                "CHECKPOINT_DATABASE_URL is not set; falling back to DATABASE_URL. "
                "TRANSITIONAL -- scheduled for removal once C3 provisions a dedicated "
                "c2pro_checkpoint credential in every environment."
            ),
        )
    else:
        logger.info("checkpoint_dsn_dedicated", reason="using CHECKPOINT_DATABASE_URL")
    return settings.checkpoint_database_url_async.replace("postgresql+asyncpg://", "postgresql://")


def _build_checkpointer() -> BaseCheckpointSaver[str]:
    """
    Build a checkpointer for persistent state management.

    For PostgreSQL, uses AsyncPostgresSaver with connection pool.
    Falls back to MemorySaver for SQLite or if postgres package not installed.

    Note: The pool is created with min_size=0, max_size=10 to avoid blocking on sync initialization.
    The pool will automatically open connections as needed.

    Uses settings.checkpoint_database_url_async (not database_url_async) --
    see _checkpoint_pool_conninfo for the TRANSITIONAL fallback contract.
    """
    from src.config import settings

    if settings.checkpoint_database_url_async.startswith("sqlite"):
        logger.warning("checkpointer_fallback", reason="SQLite not supported for postgres checkpointer")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    try:
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        global _checkpointer_pool
        if _checkpointer_pool is None:
            conn_string = _checkpoint_pool_conninfo()

            # String form: cast()'s type argument is evaluated at runtime, and
            # AsyncConnection is only imported under TYPE_CHECKING.
            _checkpointer_pool = cast(
                "AsyncConnectionPool[AsyncConnection[dict[str, Any]]]",
                AsyncConnectionPool(
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
                ),
            )

        return _async_postgres_saver_factory()(conn=_checkpointer_pool)
    except ImportError as e:
        logger.warning(
            "checkpointer_fallback",
            reason=f"langgraph-checkpoint-postgres dependencies not installed: {e}, using MemorySaver",
        )
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


async def verify_checkpoint_schema_ready(
    pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]],
) -> bool:
    """Read-only check: is the checkpoint schema fully migrated?

    Queries information_schema.columns for the column added by the newest of
    AsyncPostgresSaver's built-in migrations. information_schema is readable
    by any role with USAGE on the schema (no table-level GRANT needed), so
    this works under a runtime role with zero privileges on
    checkpoint_migrations and no DDL rights at all -- exactly the
    c2pro_checkpoint contract this slice establishes. Never issues DDL.
    """
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
            (_CHECKPOINT_SCHEMA_MARKER_TABLE, _CHECKPOINT_SCHEMA_MARKER_COLUMN),
        )
        row = await cur.fetchone()
        return row is not None


async def ensure_checkpointer_ready() -> None:
    """Verify (read-only) that the checkpoint schema is ready -- exactly once.

    Does NOT run AsyncPostgresSaver.setup() and never issues DDL: schema
    provisioning/migration is the owner's job (scripts/checkpoint_bootstrap.py
    under the c2pro_owner credential), run at deploy/bootstrap time, before
    the application starts. See CheckpointSchemaNotReadyError's docstring for
    why a missing/outdated schema must raise rather than degrade silently.

    A connection failure (DB briefly unreachable -- network restriction in a
    sandbox, PgBouncer misconfiguration, Supabase direct connection
    unavailable) is a distinct failure mode from a missing/outdated schema:
    it is logged and swallowed so the app can still start with in-memory
    checkpointing, matching this function's pre-C2 behavior for connectivity
    issues specifically. Only a *reachable* database whose checkpoint schema
    is not current raises CheckpointSchemaNotReadyError.
    """
    global _checkpointer_ready

    if _checkpointer_ready:
        return

    app = get_graph_app()
    checkpointer = getattr(app, "checkpointer", None)
    if checkpointer is None:
        return

    if _checkpointer_pool is None:
        # Non-Postgres checkpointer (e.g. MemorySaver fallback) -- nothing to verify.
        _checkpointer_ready = True
        return

    async with _checkpointer_setup_lock:
        if _checkpointer_ready:
            return
        try:
            if getattr(_checkpointer_pool, "closed", False):
                await _checkpointer_pool.open()
        except Exception as exc:  # noqa: BLE001 — pool timeout, SSL error, etc.
            _checkpointer_ready = True  # prevent retry storm on every request
            logger.warning(
                "langgraph_checkpointer_connection_failed",
                error=str(exc),
                reason="could not reach checkpoint database; app continues with in-memory fallback",
            )
            return

        try:
            ready = await verify_checkpoint_schema_ready(_checkpointer_pool)
        except Exception as exc:  # noqa: BLE001 — connectivity error surfaced mid-query
            _checkpointer_ready = True  # prevent retry storm on every request
            logger.warning(
                "langgraph_checkpointer_connection_failed",
                error=str(exc),
                reason="could not verify checkpoint schema; app continues with in-memory fallback",
            )
            return

        if not ready:
            raise CheckpointSchemaNotReadyError(
                f"Checkpoint schema is missing or not fully migrated: "
                f"{_CHECKPOINT_SCHEMA_MARKER_TABLE}.{_CHECKPOINT_SCHEMA_MARKER_COLUMN} not found. "
                f"Run scripts/checkpoint_bootstrap.py with the c2pro_owner credential "
                f"before starting the application."
            )

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


def _persist_graph_diagram(app: ProjectGraph) -> None:
    from src.config import settings

    try:
        png_bytes = app.get_graph().draw_png(None)
    except Exception:
        logger.warning("langgraph_diagram_failed", exc_info=True)
        return

    output_dir = Path(settings.local_storage_path) / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "langgraph.png"
    output_path.write_bytes(png_bytes)
    logger.info("langgraph_diagram_written", path=str(output_path))


def compile_workflow(
    checkpointer: Checkpointer = None,
    persist_diagram: bool = True,
) -> ProjectGraph:
    workflow = build_workflow()
    app = workflow.compile(checkpointer=checkpointer)
    if persist_diagram:
        _persist_graph_diagram(app)
    return app


def get_graph_app() -> ProjectGraph:
    global _graph_app
    if _graph_app is not None:
        return _graph_app

    # Disable diagram persistence to avoid pygraphviz dependency
    _graph_app = compile_workflow(checkpointer=_build_checkpointer(), persist_diagram=False)
    return _graph_app


async def run_orchestration(initial_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
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
    config: RunnableConfig = {
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
    result = await app.ainvoke(cast(ProjectState, initial_state), config)

    logger.info(
        "orchestration_completed",
        thread_id=thread_id,
        project_id=result.get("project_id"),
        doc_type=result.get("doc_type"),
        human_approval_required=result.get("human_approval_required", False),
    )

    return cast(dict[str, Any], result)
