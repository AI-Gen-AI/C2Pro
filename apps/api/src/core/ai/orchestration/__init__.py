"""
AI Orchestration Module - LangGraph State Machine Core

This module provides the core state management and type definitions
for the LangGraph-based AI orchestration layer in C2Pro.

Aligned with: PLAN_LANGGRAPH_ORCHESTRATION_I13_2026-02-15.md
"""

from .edges import route_by_intent
from .mappings import (
    CLAUSE_TYPE_TO_CATEGORY,
    ENTITY_TYPE_TO_CATEGORY,
    get_category_for_clause_type,
)
from .state import (
    CoherenceCategory,
    DEFAULT_CATEGORY_WEIGHTS,
    GraphState,
    HITLStatus,
    IntentType,
)

__all__ = [
    "IntentType",
    "HITLStatus",
    "CoherenceCategory",
    "DEFAULT_CATEGORY_WEIGHTS",
    "GraphState",
    "CLAUSE_TYPE_TO_CATEGORY",
    "ENTITY_TYPE_TO_CATEGORY",
    "get_category_for_clause_type",
    "route_by_intent",
]
