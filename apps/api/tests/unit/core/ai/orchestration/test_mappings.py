"""
TS-I13-MAP-001: Category Mappings Unit Tests

TDD Red Phase - These tests MUST FAIL initially.
The mappings module does not exist yet.

Test Suite ID: TS-I13-MAP-001
Total Tests: 8
Priority: P0 (Critical)

Aligned with: PLAN_LANGGRAPH_TDD_TESTPLAN_I13_2026-02-15.md
"""

from __future__ import annotations

import pytest

from src.core.ai.orchestration.state import CoherenceCategory


class TestClauseTypeTIMEMapping:
    """Tests for clause type to TIME category mapping - TS-I13-MAP-001-01"""

    def test_clause_type_time_mapping(self) -> None:
        """
        TS-I13-MAP-001-01: Clause types map correctly to TIME category.

        Expected mappings:
        - "Delivery Term" → CoherenceCategory.TIME
        - "Milestone" → CoherenceCategory.TIME
        - "Schedule" → CoherenceCategory.TIME
        - "Deadline" → CoherenceCategory.TIME
        - "Duration" → CoherenceCategory.TIME

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        # Import should work once implementation exists
        from src.core.ai.orchestration.mappings import CLAUSE_TYPE_TO_CATEGORY

        # All TIME-related clause types must map to CoherenceCategory.TIME
        time_clause_types = [
            "Delivery Term",
            "Milestone",
            "Schedule",
            "Deadline",
            "Duration",
        ]

        for clause_type in time_clause_types:
            assert clause_type in CLAUSE_TYPE_TO_CATEGORY, (
                f"Missing mapping for clause type: {clause_type}"
            )
            assert CLAUSE_TYPE_TO_CATEGORY[clause_type] == CoherenceCategory.TIME, (
                f"Clause type '{clause_type}' should map to TIME, "
                f"got {CLAUSE_TYPE_TO_CATEGORY[clause_type]}"
            )


class TestClauseTypeBUDGETMapping:
    """Tests for clause type to BUDGET category mapping - TS-I13-MAP-001-02"""

    def test_clause_type_budget_mapping(self) -> None:
        """
        TS-I13-MAP-001-02: Clause types map correctly to BUDGET category.

        Expected mappings:
        - "Payment Obligation" → CoherenceCategory.BUDGET
        - "Price" → CoherenceCategory.BUDGET
        - "Cost" → CoherenceCategory.BUDGET
        - "Invoice" → CoherenceCategory.BUDGET
        - "Budget" → CoherenceCategory.BUDGET

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import CLAUSE_TYPE_TO_CATEGORY

        # All BUDGET-related clause types must map to CoherenceCategory.BUDGET
        budget_clause_types = [
            "Payment Obligation",
            "Price",
            "Cost",
            "Invoice",
            "Budget",
        ]

        for clause_type in budget_clause_types:
            assert clause_type in CLAUSE_TYPE_TO_CATEGORY, (
                f"Missing mapping for clause type: {clause_type}"
            )
            assert CLAUSE_TYPE_TO_CATEGORY[clause_type] == CoherenceCategory.BUDGET, (
                f"Clause type '{clause_type}' should map to BUDGET, "
                f"got {CLAUSE_TYPE_TO_CATEGORY[clause_type]}"
            )


class TestClauseTypeSCOPEMapping:
    """Tests for clause type to SCOPE category mapping - TS-I13-MAP-001-03"""

    def test_clause_type_scope_mapping(self) -> None:
        """
        TS-I13-MAP-001-03: Clause types map correctly to SCOPE category.

        Expected mappings:
        - "Scope Definition" → CoherenceCategory.SCOPE
        - "Deliverable" → CoherenceCategory.SCOPE
        - "Work Package" → CoherenceCategory.SCOPE
        - "Exclusion" → CoherenceCategory.SCOPE

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import CLAUSE_TYPE_TO_CATEGORY

        # All SCOPE-related clause types must map to CoherenceCategory.SCOPE
        scope_clause_types = [
            "Scope Definition",
            "Deliverable",
            "Work Package",
            "Exclusion",
        ]

        for clause_type in scope_clause_types:
            assert clause_type in CLAUSE_TYPE_TO_CATEGORY, (
                f"Missing mapping for clause type: {clause_type}"
            )
            assert CLAUSE_TYPE_TO_CATEGORY[clause_type] == CoherenceCategory.SCOPE, (
                f"Clause type '{clause_type}' should map to SCOPE, "
                f"got {CLAUSE_TYPE_TO_CATEGORY[clause_type]}"
            )


class TestClauseTypeQUALITYMapping:
    """Tests for clause type to QUALITY category mapping - TS-I13-MAP-001-04"""

    def test_clause_type_quality_mapping(self) -> None:
        """
        TS-I13-MAP-001-04: Clause types map correctly to QUALITY category.

        Expected mappings:
        - "Quality Standard" → CoherenceCategory.QUALITY
        - "Certification" → CoherenceCategory.QUALITY
        - "Inspection" → CoherenceCategory.QUALITY
        - "Testing" → CoherenceCategory.QUALITY

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import CLAUSE_TYPE_TO_CATEGORY

        # All QUALITY-related clause types must map to CoherenceCategory.QUALITY
        quality_clause_types = [
            "Quality Standard",
            "Certification",
            "Inspection",
            "Testing",
        ]

        for clause_type in quality_clause_types:
            assert clause_type in CLAUSE_TYPE_TO_CATEGORY, (
                f"Missing mapping for clause type: {clause_type}"
            )
            assert CLAUSE_TYPE_TO_CATEGORY[clause_type] == CoherenceCategory.QUALITY, (
                f"Clause type '{clause_type}' should map to QUALITY, "
                f"got {CLAUSE_TYPE_TO_CATEGORY[clause_type]}"
            )


class TestClauseTypeTECHNICALMapping:
    """Tests for clause type to TECHNICAL category mapping - TS-I13-MAP-001-05"""

    def test_clause_type_technical_mapping(self) -> None:
        """
        TS-I13-MAP-001-05: Clause types map correctly to TECHNICAL category.

        Expected mappings:
        - "Technical Specification" → CoherenceCategory.TECHNICAL
        - "Requirement" → CoherenceCategory.TECHNICAL
        - "Dependency" → CoherenceCategory.TECHNICAL
        - "Interface" → CoherenceCategory.TECHNICAL

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import CLAUSE_TYPE_TO_CATEGORY

        # All TECHNICAL-related clause types must map to CoherenceCategory.TECHNICAL
        technical_clause_types = [
            "Technical Specification",
            "Requirement",
            "Dependency",
            "Interface",
        ]

        for clause_type in technical_clause_types:
            assert clause_type in CLAUSE_TYPE_TO_CATEGORY, (
                f"Missing mapping for clause type: {clause_type}"
            )
            assert CLAUSE_TYPE_TO_CATEGORY[clause_type] == CoherenceCategory.TECHNICAL, (
                f"Clause type '{clause_type}' should map to TECHNICAL, "
                f"got {CLAUSE_TYPE_TO_CATEGORY[clause_type]}"
            )


class TestClauseTypeLEGALMapping:
    """Tests for clause type to LEGAL category mapping - TS-I13-MAP-001-06"""

    def test_clause_type_legal_mapping(self) -> None:
        """
        TS-I13-MAP-001-06: Clause types map correctly to LEGAL category.

        Expected mappings:
        - "Penalty" → CoherenceCategory.LEGAL
        - "Termination" → CoherenceCategory.LEGAL
        - "Warranty" → CoherenceCategory.LEGAL
        - "Approval" → CoherenceCategory.LEGAL
        - "Liability" → CoherenceCategory.LEGAL
        - "Indemnification" → CoherenceCategory.LEGAL

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import CLAUSE_TYPE_TO_CATEGORY

        # All LEGAL-related clause types must map to CoherenceCategory.LEGAL
        legal_clause_types = [
            "Penalty",
            "Termination",
            "Warranty",
            "Approval",
            "Liability",
            "Indemnification",
        ]

        for clause_type in legal_clause_types:
            assert clause_type in CLAUSE_TYPE_TO_CATEGORY, (
                f"Missing mapping for clause type: {clause_type}"
            )
            assert CLAUSE_TYPE_TO_CATEGORY[clause_type] == CoherenceCategory.LEGAL, (
                f"Clause type '{clause_type}' should map to LEGAL, "
                f"got {CLAUSE_TYPE_TO_CATEGORY[clause_type]}"
            )


class TestEntityTypeToCategoryMapping:
    """Tests for entity type to category mapping - TS-I13-MAP-001-07"""

    def test_entity_type_to_category_mapping(self) -> None:
        """
        TS-I13-MAP-001-07: Entity types map correctly to coherence categories.

        Expected mappings:
        - "dates" → CoherenceCategory.TIME
        - "money" → CoherenceCategory.BUDGET
        - "standards" → CoherenceCategory.QUALITY
        - "penalties" → CoherenceCategory.LEGAL
        - "specs" → CoherenceCategory.TECHNICAL

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import ENTITY_TYPE_TO_CATEGORY

        # Verify entity type to category mappings
        expected_mappings = {
            "dates": CoherenceCategory.TIME,
            "money": CoherenceCategory.BUDGET,
            "standards": CoherenceCategory.QUALITY,
            "penalties": CoherenceCategory.LEGAL,
            "specs": CoherenceCategory.TECHNICAL,
        }

        for entity_type, expected_category in expected_mappings.items():
            assert entity_type in ENTITY_TYPE_TO_CATEGORY, (
                f"Missing mapping for entity type: {entity_type}"
            )
            assert ENTITY_TYPE_TO_CATEGORY[entity_type] == expected_category, (
                f"Entity type '{entity_type}' should map to {expected_category.name}, "
                f"got {ENTITY_TYPE_TO_CATEGORY[entity_type]}"
            )


class TestUnknownClauseTypeDefault:
    """Tests for unknown clause type default behavior - TS-I13-MAP-001-08"""

    def test_unknown_clause_type_default(self) -> None:
        """
        TS-I13-MAP-001-08: Unknown clause types default to SCOPE or raise.

        The get_category_for_clause_type function should:
        - Return the mapped category for known clause types
        - Return SCOPE as default for unknown clause types

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 3.1.
        """
        from src.core.ai.orchestration.mappings import get_category_for_clause_type

        # Known clause type should return its mapped category
        assert get_category_for_clause_type("Deadline") == CoherenceCategory.TIME
        assert get_category_for_clause_type("Budget") == CoherenceCategory.BUDGET
        assert get_category_for_clause_type("Penalty") == CoherenceCategory.LEGAL

        # Unknown clause types should default to SCOPE
        assert get_category_for_clause_type("Unknown Clause") == CoherenceCategory.SCOPE
        assert get_category_for_clause_type("Random Type") == CoherenceCategory.SCOPE
        assert get_category_for_clause_type("") == CoherenceCategory.SCOPE
