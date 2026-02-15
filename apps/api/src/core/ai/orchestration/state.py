"""
GraphState & Enums for LangGraph Orchestration

This module defines the core state types and enums for the
LangGraph-based AI orchestration layer.

Module ID: TS-I13-STATE-001
Aligned with: PLAN_LANGGRAPH_ORCHESTRATION_I13_2026-02-15.md
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class IntentType(str, Enum):
    """
    Intent classification types for routing user queries.

    Used by N1 (Intent Classifier) to determine the processing path.
    """
    DOCUMENT = "document"
    PROJECT = "project"
    STAKEHOLDER = "stakeholder"
    PROCUREMENT = "procurement"
    ANALYSIS = "analysis"
    COHERENCE = "coherence"
    UNKNOWN = "unknown"


class HITLStatus(str, Enum):
    """
    Human-in-the-loop status for checkpoint management.

    Used by N15 (HITL Gate) and N16 (Wait for Human) nodes.
    """
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class CoherenceCategory(str, Enum):
    """
    Coherence analysis categories for subscore calculation.

    Each category has an associated weight in DEFAULT_CATEGORY_WEIGHTS.
    Per PLAN_ARQUITECTURA v2.1 Section 9.1.
    """
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    QUALITY = "QUALITY"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    TIME = "TIME"


# Category weights for weighted average coherence score calculation
# Per PLAN_ARQUITECTURA v2.1 Section 9.1
DEFAULT_CATEGORY_WEIGHTS: Dict[str, float] = {
    "SCOPE": 0.20,
    "BUDGET": 0.20,
    "QUALITY": 0.15,
    "TECHNICAL": 0.15,
    "LEGAL": 0.15,
    "TIME": 0.15,
}


class GraphState(TypedDict, total=False):
    """
    LangGraph state container for orchestration workflow.

    All fields are optional (total=False) to allow partial state
    updates during graph execution.

    Field Groups:
    - Identity: run_id, tenant_id, project_id, user_id
    - Input: document_bytes, query
    - Intent: intent, intent_confidence, intent_metadata
    - Extraction: extracted_*, clauses_by_category
    - Coherence: coherence_*, alerts_by_category
    - HITL: hitl_*
    - Output: response, execution_path, errors
    """

    # === Identity Fields ===
    run_id: str
    tenant_id: str
    project_id: str
    user_id: str

    # === Input Fields ===
    document_bytes: bytes
    query: str

    # === Intent Classification Fields ===
    intent: IntentType
    intent_confidence: float
    intent_metadata: Dict[str, Any]

    # === Extraction Fields ===
    extracted_clauses: List[Dict[str, Any]]
    clauses_by_category: Dict[str, List[Dict[str, Any]]]
    extracted_dates: List[Dict[str, Any]]
    extracted_money: List[Dict[str, Any]]
    extracted_durations: List[Dict[str, Any]]
    extracted_milestones: List[Dict[str, Any]]
    extracted_standards: List[Dict[str, Any]]
    extracted_penalties: List[Dict[str, Any]]
    extracted_actors: List[Dict[str, Any]]
    extracted_materials: List[Dict[str, Any]]
    extracted_specs: List[Dict[str, Any]]
    extracted_entities: List[Dict[str, Any]]
    extraction_confidence: float

    # === Coherence Analysis Fields ===
    coherence_alerts: List[Dict[str, Any]]
    alerts_by_category: Dict[str, List[Dict[str, Any]]]
    coherence_subscores: Dict[str, float]
    coherence_score: float
    category_weights: Dict[str, float]
    coherence_methodology_version: str

    # === HITL (Human-in-the-Loop) Fields ===
    hitl_status: HITLStatus
    hitl_item_id: str
    hitl_required_reason: str
    hitl_approved_by: Optional[str]
    hitl_approved_at: Optional[str]

    # === Output Fields ===
    response: str
    execution_path: List[str]
    errors: List[Dict[str, Any]]

    # === Metadata Fields ===
    created_at: str
    updated_at: str
    processing_time_ms: int
