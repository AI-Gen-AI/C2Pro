"""
graph.py — LangGraph Subgraph Builder for Coherence Engine v0.3

Builds and compiles the coherence evaluation subgraph with the following topology:

    prepare_context → [deterministic, llm] (parallel) → cross_clause → scoring → format

The subgraph can be:
1. Invoked standalone for coherence evaluation
2. Composed into a larger LangGraph pipeline
3. Used with checkpointing for resumable evaluation

Location: apps/api/src/coherence/graph/graph.py
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, StateGraph

from src.coherence.domain.v2_constants import SCORE_VERSION_V1

from ..models import Clause, EnrichedCoherenceResult, FindingSignal
from .nodes import (
    cross_clause_eval,
    deterministic_evaluate,
    format_output,
    llm_semantic_evaluate,
    prepare_context,
    rag_similarity_check,
    scoring_arbiter,
)
from .state import CoherenceGraphState, EvaluationConfig

logger = logging.getLogger(__name__)


def _honest_null_result(final_state: dict[str, Any]) -> EnrichedCoherenceResult:
    diagnostics = final_state.get("diagnostics") or {}
    reason = diagnostics.get("reason") or "coherence_result_missing"
    return EnrichedCoherenceResult(
        overall_score=None,
        alerts=[],
        calculated_at=datetime.now(UTC),
        score_version=SCORE_VERSION_V1,
        score_reason=reason,
        score_missing_dimensions=diagnostics.get("missing_dimensions"),
        finding_signals=[],
    )


# =============================================================================
# GRAPH BUILDER
# =============================================================================


def build_coherence_subgraph() -> StateGraph:
    """
    Build the coherence evaluation subgraph.

    Graph topology (Phase 6 - with RAG):
        START → prepare_context → deterministic_evaluate → llm_semantic_evaluate
              → rag_similarity_check → cross_clause_eval → scoring_arbiter
              → format_output → END

    Note: In future iterations, deterministic, LLM, and RAG can run
    in parallel using LangGraph's fan-out/fan-in pattern. For v0.3 Phase 6,
    we run them sequentially with LLM/RAG skipped in low_budget_mode.

    Returns:
        StateGraph: Uncompiled graph ready for compilation or composition
    """
    # Create graph with state schema
    graph = StateGraph(CoherenceGraphState)

    # Add nodes
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("deterministic_evaluate", deterministic_evaluate)
    graph.add_node("llm_semantic_evaluate", llm_semantic_evaluate)
    graph.add_node("rag_similarity_check", rag_similarity_check)
    graph.add_node("cross_clause_eval", cross_clause_eval)
    graph.add_node("scoring_arbiter", scoring_arbiter)
    graph.add_node("format_output", format_output)

    # Define edges (sequential flow for v0.3)
    # START → prepare_context
    graph.set_entry_point("prepare_context")

    # prepare_context → deterministic_evaluate
    graph.add_edge("prepare_context", "deterministic_evaluate")

    # deterministic_evaluate → llm_semantic_evaluate
    graph.add_edge("deterministic_evaluate", "llm_semantic_evaluate")

    # llm_semantic_evaluate → rag_similarity_check
    graph.add_edge("llm_semantic_evaluate", "rag_similarity_check")

    # rag_similarity_check → cross_clause_eval
    graph.add_edge("rag_similarity_check", "cross_clause_eval")

    # cross_clause_eval → scoring_arbiter
    graph.add_edge("cross_clause_eval", "scoring_arbiter")

    # scoring_arbiter → format_output
    graph.add_edge("scoring_arbiter", "format_output")

    # format_output → END
    graph.add_edge("format_output", END)

    logger.info("Coherence subgraph (with RAG) built successfully")

    return graph


def build_parallel_coherence_subgraph() -> StateGraph:
    """
    Build coherence subgraph with parallel evaluation (future enhancement).

    Graph topology (Phase 6 - with RAG):
        START → prepare_context → [det, llm, rag] (parallel) → fan_in
              → cross_clause → scoring → format → END

    This version uses LangGraph's conditional branching to run
    deterministic, LLM, and RAG evaluation in parallel, then fan-in.

    Returns:
        StateGraph: Uncompiled graph with parallel evaluation
    """
    graph = StateGraph(CoherenceGraphState)

    # Add nodes
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("deterministic_evaluate", deterministic_evaluate)
    graph.add_node("llm_semantic_evaluate", llm_semantic_evaluate)
    graph.add_node("rag_similarity_check", rag_similarity_check)
    graph.add_node("fan_in", _fan_in_node)  # Synchronization point
    graph.add_node("cross_clause_eval", cross_clause_eval)
    graph.add_node("scoring_arbiter", scoring_arbiter)
    graph.add_node("format_output", format_output)

    # Entry point
    graph.set_entry_point("prepare_context")

    # Fan-out: prepare_context → all three evaluators
    graph.add_edge("prepare_context", "deterministic_evaluate")
    graph.add_edge("prepare_context", "llm_semantic_evaluate")
    graph.add_edge("prepare_context", "rag_similarity_check")

    # Fan-in: all evaluators → fan_in
    graph.add_edge("deterministic_evaluate", "fan_in")
    graph.add_edge("llm_semantic_evaluate", "fan_in")
    graph.add_edge("rag_similarity_check", "fan_in")

    # Continue sequential
    graph.add_edge("fan_in", "cross_clause_eval")
    graph.add_edge("cross_clause_eval", "scoring_arbiter")
    graph.add_edge("scoring_arbiter", "format_output")
    graph.add_edge("format_output", END)

    logger.info("Parallel coherence subgraph (with RAG) built successfully")

    return graph


def _fan_in_node(state: CoherenceGraphState) -> dict[str, Any]:
    """
    Fan-in synchronization node for parallel evaluation.

    This node doesn't do any work; it just serves as a synchronization
    point where the graph waits for deterministic, LLM, and RAG
    evaluation to complete before proceeding.
    """
    logger.info(
        f"fan_in: {len(state.deterministic_signals)} det signals, "
        f"{len(state.llm_signals)} llm signals, "
        f"{len(state.cross_pairs)} RAG pairs"
    )
    return {}  # No state changes, just synchronization


# =============================================================================
# COMPILED SUBGRAPH
# =============================================================================


# Compile the default subgraph
_compiled_graph = None


def get_coherence_subgraph():
    """
    Get the compiled coherence subgraph (lazy initialization).

    Returns:
        CompiledGraph: Ready-to-invoke coherence evaluation graph
    """
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_coherence_subgraph()
        _compiled_graph = graph.compile()
        logger.info("Coherence subgraph compiled")
    return _compiled_graph


# Export the compiled subgraph for direct use
coherence_subgraph = None  # Lazy-loaded via get_coherence_subgraph()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def evaluate_coherence(
    clauses: list[Clause],
    project_id: str = "default",
    config: EvaluationConfig | None = None,
) -> EnrichedCoherenceResult:
    """
    Evaluate coherence for a list of clauses.

    This is the main entry point for coherence evaluation. It:
    1. Creates initial state from input clauses
    2. Runs the coherence subgraph
    3. Returns the enriched result

    Args:
        clauses: List of Clause objects to evaluate
        project_id: Optional project identifier
        config: Optional evaluation configuration

    Returns:
        EnrichedCoherenceResult with score, alerts, and diagnostics

    Example:
        >>> from coherence.models import Clause
        >>> clauses = [
        ...     Clause(id="bud-1", text="Budget: $100,000", data={"planned": 100000, "current": 120000}),
        ...     Clause(id="sch-1", text="Deadline: 2024-06-01", data={"end_date": "2024-06-01"}),
        ... ]
        >>> result = evaluate_coherence(clauses)
        >>> print(f"Score: {result.overall_score}")
    """
    # Create initial state
    initial_state = CoherenceGraphState(
        project_id=project_id,
        clauses=clauses,
        config=config or EvaluationConfig(),
    )

    # Get compiled graph
    graph = get_coherence_subgraph()

    # Run evaluation
    final_state = graph.invoke(initial_state)

    # Extract result
    result = final_state.get("result")
    if result is None:
        result = _honest_null_result(final_state)

    return result


async def evaluate_coherence_async(
    clauses: list[Clause],
    project_id: str = "default",
    config: EvaluationConfig | None = None,
    seed_signals: list[FindingSignal] | None = None,
    seed_coverage: dict[str, bool] | None = None,
) -> EnrichedCoherenceResult:
    """
    Async version of evaluate_coherence.

    Uses LangGraph's async invocation for better performance in
    async contexts (e.g., FastAPI endpoints).

    Args:
        clauses: List of Clause objects to evaluate
        project_id: Optional project identifier
        config: Optional evaluation configuration

    Returns:
        EnrichedCoherenceResult with score, alerts, and diagnostics
    """
    # Create initial state
    initial_state = CoherenceGraphState(
        project_id=project_id,
        clauses=clauses,
        config=config or EvaluationConfig(),
        deterministic_signals=seed_signals or [],
        coverage_map=seed_coverage or {},
    )

    # Get compiled graph
    graph = get_coherence_subgraph()

    # Run evaluation asynchronously
    final_state = await graph.ainvoke(initial_state)

    # Extract result
    result = final_state.get("result")
    if result is None:
        result = _honest_null_result(final_state)

    return result


def evaluate_coherence_with_streaming(
    clauses: list[Clause],
    project_id: str = "default",
    config: EvaluationConfig | None = None,
):
    """
    Evaluate coherence with streaming updates.

    Yields intermediate states as each node completes, useful for
    progress tracking in UI.

    Args:
        clauses: List of Clause objects to evaluate
        project_id: Optional project identifier
        config: Optional evaluation configuration

    Yields:
        Tuple of (node_name, partial_state) as each node completes
    """
    initial_state = CoherenceGraphState(
        project_id=project_id,
        clauses=clauses,
        config=config or EvaluationConfig(),
    )

    graph = get_coherence_subgraph()

    for output in graph.stream(initial_state):
        yield from output.items()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "build_coherence_subgraph",
    "build_parallel_coherence_subgraph",
    "get_coherence_subgraph",
    "coherence_subgraph",
    "evaluate_coherence",
    "evaluate_coherence_async",
    "evaluate_coherence_with_streaming",
]
