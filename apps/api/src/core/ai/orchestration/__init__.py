"""
AI Orchestration Module - LangGraph State Machine Core

This module provides the core state management and type definitions
for the LangGraph-based AI orchestration layer in C2Pro.

Aligned with: PLAN_LANGGRAPH_ORCHESTRATION_I13_2026-02-15.md
"""

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
]
