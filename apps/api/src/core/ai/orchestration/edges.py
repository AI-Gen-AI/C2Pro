"""
Conditional Edge Functions for LangGraph Orchestration

This module defines the routing functions used as conditional edges
in the LangGraph state machine.

Module ID: TS-I13-EDGE-001
Aligned with: PLAN_LANGGRAPH_ORCHESTRATION_I13_2026-02-15.md
"""

from __future__ import annotations

from .state import GraphState, IntentType


def route_by_intent(state: GraphState) -> str:
    """
    Route to the appropriate node based on classified intent.

    Args:
        state: The current graph state containing intent and confidence.

    Returns:
        The name of the next node to execute.

    Routing rules:
    - confidence < 0.5 → "error_handler" (regardless of intent)
    - DOCUMENT → "document_ingestion"
    - PROJECT → "wbs_generator"
    - STAKEHOLDER → "stakeholder_extractor"
    - PROCUREMENT → "procurement_planner"
    - ANALYSIS → "evidence_retriever"
    - COHERENCE → "coherence_evaluator"
    - UNKNOWN → "error_handler"

    TS-I13-EDGE-001-01 to TS-I13-EDGE-001-08
    """
    # Check confidence threshold first (TS-I13-EDGE-001-08)
    confidence = state.get("intent_confidence", 0.0)
    if confidence < 0.5:
        return "error_handler"

    intent = state.get("intent")

    if intent == IntentType.DOCUMENT:
        return "document_ingestion"

    if intent == IntentType.PROJECT:
        return "wbs_generator"

    if intent == IntentType.STAKEHOLDER:
        return "stakeholder_extractor"

    if intent == IntentType.PROCUREMENT:
        return "procurement_planner"

    if intent == IntentType.ANALYSIS:
        return "evidence_retriever"

    if intent == IntentType.COHERENCE:
        return "coherence_evaluator"

    # Default fallback (will be expanded in subsequent tests)
    return "error_handler"


def route_by_evidence_gate(state: GraphState) -> str:
    """
    Route based on whether evidence threshold has been met.

    Args:
        state: The current graph state containing evidence_threshold_met.

    Returns:
        The name of the next node to execute.

    Routing rules:
    - evidence_threshold_met=True → "coherence_evaluator"
    - evidence_threshold_met=False → "error_handler"

    TS-I13-EDGE-001-09 to TS-I13-EDGE-001-10
    """
    if state.get("evidence_threshold_met", False):
        return "coherence_evaluator"

    return "error_handler"
