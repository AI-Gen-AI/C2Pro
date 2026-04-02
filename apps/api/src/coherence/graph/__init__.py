"""
Coherence Engine v0.3 — LangGraph Subgraph Components

This package contains:
- prompts.py: Optimized prompt templates for LLM evaluation
- state.py: Graph state dataclasses (Phase 5)
- nodes.py: Graph node implementations (Phase 5)
- graph.py: LangGraph subgraph builder (Phase 5)
"""

from .prompts import (
    COHERENCE_SYSTEM_PROMPT,
    RULE_EVALUATION_PROMPT,
    BATCH_EVALUATION_PROMPT,
    CROSS_CLAUSE_PROMPT,
    FEW_SHOT_EXAMPLES,
    build_evaluation_prompt,
    build_batch_prompt,
    build_cross_clause_prompt,
)

from .state import (
    ClauseWithEmbedding,
    CrossClausePair,
    EvaluationConfig,
    CoherenceGraphState,
)

from .nodes import (
    prepare_context,
    deterministic_evaluate,
    llm_semantic_evaluate,
    cross_clause_eval,
    scoring_arbiter,
    format_output,
    infer_category,
    infer_document_type,
)

from .graph import (
    build_coherence_subgraph,
    build_parallel_coherence_subgraph,
    get_coherence_subgraph,
    evaluate_coherence,
    evaluate_coherence_async,
    evaluate_coherence_with_streaming,
)

__all__ = [
    # Prompts
    "COHERENCE_SYSTEM_PROMPT",
    "RULE_EVALUATION_PROMPT",
    "BATCH_EVALUATION_PROMPT",
    "CROSS_CLAUSE_PROMPT",
    "FEW_SHOT_EXAMPLES",
    "build_evaluation_prompt",
    "build_batch_prompt",
    "build_cross_clause_prompt",
    # State
    "ClauseWithEmbedding",
    "CrossClausePair",
    "EvaluationConfig",
    "CoherenceGraphState",
    # Nodes
    "prepare_context",
    "deterministic_evaluate",
    "llm_semantic_evaluate",
    "cross_clause_eval",
    "scoring_arbiter",
    "format_output",
    "infer_category",
    "infer_document_type",
    # Graph
    "build_coherence_subgraph",
    "build_parallel_coherence_subgraph",
    "get_coherence_subgraph",
    "evaluate_coherence",
    "evaluate_coherence_async",
    "evaluate_coherence_with_streaming",
]
