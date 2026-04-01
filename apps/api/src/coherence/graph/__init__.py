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
)

__all__ = [
    "COHERENCE_SYSTEM_PROMPT",
    "RULE_EVALUATION_PROMPT",
    "BATCH_EVALUATION_PROMPT",
    "CROSS_CLAUSE_PROMPT",
    "FEW_SHOT_EXAMPLES",
]
