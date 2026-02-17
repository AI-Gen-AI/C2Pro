"""
Category Mappings for LangGraph Orchestration

This module defines mappings from clause types and entity types
to coherence categories for classification and routing.

Module ID: TS-I13-MAP-001
Aligned with: PLAN_LANGGRAPH_ORCHESTRATION_I13_2026-02-15.md
"""

from __future__ import annotations

from typing import Dict

from .state import CoherenceCategory


# Clause type to coherence category mapping
# Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1
CLAUSE_TYPE_TO_CATEGORY: Dict[str, CoherenceCategory] = {
    # TIME category mappings (TS-I13-MAP-001-01)
    "Delivery Term": CoherenceCategory.TIME,
    "Milestone": CoherenceCategory.TIME,
    "Schedule": CoherenceCategory.TIME,
    "Deadline": CoherenceCategory.TIME,
    "Duration": CoherenceCategory.TIME,
    # BUDGET category mappings (TS-I13-MAP-001-02)
    "Payment Obligation": CoherenceCategory.BUDGET,
    "Price": CoherenceCategory.BUDGET,
    "Cost": CoherenceCategory.BUDGET,
    "Invoice": CoherenceCategory.BUDGET,
    "Budget": CoherenceCategory.BUDGET,
    # SCOPE category mappings (TS-I13-MAP-001-03)
    "Scope Definition": CoherenceCategory.SCOPE,
    "Deliverable": CoherenceCategory.SCOPE,
    "Work Package": CoherenceCategory.SCOPE,
    "Exclusion": CoherenceCategory.SCOPE,
    # QUALITY category mappings (TS-I13-MAP-001-04)
    "Quality Standard": CoherenceCategory.QUALITY,
    "Certification": CoherenceCategory.QUALITY,
    "Inspection": CoherenceCategory.QUALITY,
    "Testing": CoherenceCategory.QUALITY,
    # TECHNICAL category mappings (TS-I13-MAP-001-05)
    "Technical Specification": CoherenceCategory.TECHNICAL,
    "Requirement": CoherenceCategory.TECHNICAL,
    "Dependency": CoherenceCategory.TECHNICAL,
    "Interface": CoherenceCategory.TECHNICAL,
    # LEGAL category mappings (TS-I13-MAP-001-06)
    "Penalty": CoherenceCategory.LEGAL,
    "Termination": CoherenceCategory.LEGAL,
    "Warranty": CoherenceCategory.LEGAL,
    "Approval": CoherenceCategory.LEGAL,
    "Liability": CoherenceCategory.LEGAL,
    "Indemnification": CoherenceCategory.LEGAL,
}


# Entity type to coherence category mapping (TS-I13-MAP-001-07)
# Maps extracted entity types to their corresponding coherence categories
ENTITY_TYPE_TO_CATEGORY: Dict[str, CoherenceCategory] = {
    "dates": CoherenceCategory.TIME,
    "money": CoherenceCategory.BUDGET,
    "standards": CoherenceCategory.QUALITY,
    "penalties": CoherenceCategory.LEGAL,
    "specs": CoherenceCategory.TECHNICAL,
}


def get_category_for_clause_type(clause_type: str) -> CoherenceCategory:
    """
    Get the coherence category for a given clause type.

    Returns the mapped category for known clause types,
    or SCOPE as the default for unknown clause types.

    Args:
        clause_type: The clause type string to look up.

    Returns:
        The corresponding CoherenceCategory, defaulting to SCOPE.

    TS-I13-MAP-001-08
    """
    return CLAUSE_TYPE_TO_CATEGORY.get(clause_type, CoherenceCategory.SCOPE)
