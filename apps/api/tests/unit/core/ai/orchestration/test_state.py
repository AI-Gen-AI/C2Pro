"""
TS-I13-STATE-001: GraphState & Enums Unit Tests

TDD Red Phase - These tests MUST FAIL initially.
The implementation does not exist yet.

Test Suite ID: TS-I13-STATE-001
Total Tests: 12
Priority: P0 (Critical)

Aligned with: PLAN_LANGGRAPH_ORCHESTRATION_I13_2026-02-15.md
"""

from __future__ import annotations

import json
import pytest
from typing import Any


class TestIntentTypeEnum:
    """Tests for IntentType enum - TS-I13-STATE-001-01"""

    def test_intent_type_enum_values(self) -> None:
        """
        TS-I13-STATE-001-01: IntentType has all 7 values.

        Expected values: DOCUMENT, PROJECT, STAKEHOLDER, PROCUREMENT,
                        ANALYSIS, COHERENCE, UNKNOWN
        """
        # Import should work once implementation exists
        from src.core.ai.orchestration.state import IntentType

        # Verify all 7 enum values exist
        assert hasattr(IntentType, "DOCUMENT")
        assert hasattr(IntentType, "PROJECT")
        assert hasattr(IntentType, "STAKEHOLDER")
        assert hasattr(IntentType, "PROCUREMENT")
        assert hasattr(IntentType, "ANALYSIS")
        assert hasattr(IntentType, "COHERENCE")
        assert hasattr(IntentType, "UNKNOWN")

        # Verify enum values are strings
        assert IntentType.DOCUMENT.value == "document"
        assert IntentType.PROJECT.value == "project"
        assert IntentType.STAKEHOLDER.value == "stakeholder"
        assert IntentType.PROCUREMENT.value == "procurement"
        assert IntentType.ANALYSIS.value == "analysis"
        assert IntentType.COHERENCE.value == "coherence"
        assert IntentType.UNKNOWN.value == "unknown"

        # Verify total count
        assert len(IntentType) == 7


class TestHITLStatusEnum:
    """Tests for HITLStatus enum - TS-I13-STATE-001-02"""

    def test_hitl_status_enum_values(self) -> None:
        """
        TS-I13-STATE-001-02: HITLStatus has all 5 values.

        Expected values: NOT_REQUIRED, PENDING, APPROVED, REJECTED, ESCALATED
        """
        from src.core.ai.orchestration.state import HITLStatus

        # Verify all 5 enum values exist
        assert hasattr(HITLStatus, "NOT_REQUIRED")
        assert hasattr(HITLStatus, "PENDING")
        assert hasattr(HITLStatus, "APPROVED")
        assert hasattr(HITLStatus, "REJECTED")
        assert hasattr(HITLStatus, "ESCALATED")

        # Verify enum values are strings
        assert HITLStatus.NOT_REQUIRED.value == "not_required"
        assert HITLStatus.PENDING.value == "pending"
        assert HITLStatus.APPROVED.value == "approved"
        assert HITLStatus.REJECTED.value == "rejected"
        assert HITLStatus.ESCALATED.value == "escalated"

        # Verify total count
        assert len(HITLStatus) == 5


class TestCoherenceCategoryEnum:
    """Tests for CoherenceCategory enum - TS-I13-STATE-001-03"""

    def test_coherence_category_enum_values(self) -> None:
        """
        TS-I13-STATE-001-03: CoherenceCategory has all 6 values.

        Expected values: SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME
        """
        from src.core.ai.orchestration.state import CoherenceCategory

        # Verify all 6 enum values exist
        assert hasattr(CoherenceCategory, "SCOPE")
        assert hasattr(CoherenceCategory, "BUDGET")
        assert hasattr(CoherenceCategory, "QUALITY")
        assert hasattr(CoherenceCategory, "TECHNICAL")
        assert hasattr(CoherenceCategory, "LEGAL")
        assert hasattr(CoherenceCategory, "TIME")

        # Verify enum values are uppercase strings
        assert CoherenceCategory.SCOPE.value == "SCOPE"
        assert CoherenceCategory.BUDGET.value == "BUDGET"
        assert CoherenceCategory.QUALITY.value == "QUALITY"
        assert CoherenceCategory.TECHNICAL.value == "TECHNICAL"
        assert CoherenceCategory.LEGAL.value == "LEGAL"
        assert CoherenceCategory.TIME.value == "TIME"

        # Verify total count
        assert len(CoherenceCategory) == 6


class TestDefaultCategoryWeights:
    """Tests for DEFAULT_CATEGORY_WEIGHTS - TS-I13-STATE-001-04, 05"""

    def test_default_category_weights_sum_to_one(self) -> None:
        """
        TS-I13-STATE-001-04: DEFAULT_CATEGORY_WEIGHTS sum = 1.0

        The weights for all 6 categories must sum to exactly 1.0
        to ensure proper weighted average calculation.
        """
        from src.core.ai.orchestration.state import DEFAULT_CATEGORY_WEIGHTS

        total = sum(DEFAULT_CATEGORY_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_default_category_weights_values(self) -> None:
        """
        TS-I13-STATE-001-05: Verify specific weight values.

        Expected weights per PLAN_ARQUITECTURA v2.1 §9.1:
        - SCOPE: 0.20 (20%)
        - BUDGET: 0.20 (20%)
        - QUALITY: 0.15 (15%)
        - TECHNICAL: 0.15 (15%)
        - LEGAL: 0.15 (15%)
        - TIME: 0.15 (15%)
        """
        from src.core.ai.orchestration.state import DEFAULT_CATEGORY_WEIGHTS

        assert DEFAULT_CATEGORY_WEIGHTS["SCOPE"] == 0.20
        assert DEFAULT_CATEGORY_WEIGHTS["BUDGET"] == 0.20
        assert DEFAULT_CATEGORY_WEIGHTS["QUALITY"] == 0.15
        assert DEFAULT_CATEGORY_WEIGHTS["TECHNICAL"] == 0.15
        assert DEFAULT_CATEGORY_WEIGHTS["LEGAL"] == 0.15
        assert DEFAULT_CATEGORY_WEIGHTS["TIME"] == 0.15

        # Verify all 6 categories are present
        assert len(DEFAULT_CATEGORY_WEIGHTS) == 6


class TestGraphStateIdentityFields:
    """Tests for GraphState identity fields - TS-I13-STATE-001-06"""

    def test_graph_state_identity_fields(self) -> None:
        """
        TS-I13-STATE-001-06: GraphState accepts identity fields.

        Fields: run_id, tenant_id, project_id, user_id
        """
        from src.core.ai.orchestration.state import GraphState

        # Create a valid GraphState with identity fields
        state: GraphState = {
            "run_id": "run-123",
            "tenant_id": "tenant-456",
            "project_id": "project-789",
            "user_id": "user-abc",
        }

        # Verify fields are accessible
        assert state["run_id"] == "run-123"
        assert state["tenant_id"] == "tenant-456"
        assert state["project_id"] == "project-789"
        assert state["user_id"] == "user-abc"


class TestGraphStateInputFields:
    """Tests for GraphState input fields - TS-I13-STATE-001-07"""

    def test_graph_state_input_fields(self) -> None:
        """
        TS-I13-STATE-001-07: GraphState accepts input fields.

        Fields: document_bytes, query
        """
        from src.core.ai.orchestration.state import GraphState

        # Create a valid GraphState with input fields
        state: GraphState = {
            "document_bytes": b"PDF content here",
            "query": "Analyze this contract for payment terms",
        }

        # Verify fields are accessible
        assert state["document_bytes"] == b"PDF content here"
        assert state["query"] == "Analyze this contract for payment terms"


class TestGraphStateExtractionFields:
    """Tests for GraphState extraction fields - TS-I13-STATE-001-08"""

    def test_graph_state_extraction_fields(self) -> None:
        """
        TS-I13-STATE-001-08: GraphState accepts extraction fields.

        Fields: clauses_by_category, extracted_dates, extracted_money,
                extracted_durations, extracted_milestones, extracted_standards,
                extracted_penalties, extracted_actors, extracted_materials,
                extracted_specs, extracted_clauses, extracted_entities
        """
        from src.core.ai.orchestration.state import GraphState

        # Create a valid GraphState with extraction fields
        state: GraphState = {
            "extracted_clauses": [{"id": "c1", "text": "Payment due in 30 days"}],
            "clauses_by_category": {
                "TIME": [{"id": "c1"}],
                "BUDGET": [],
                "SCOPE": [],
                "QUALITY": [],
                "TECHNICAL": [],
                "LEGAL": [],
            },
            "extracted_dates": [{"value": "2026-03-01", "context": "deadline"}],
            "extracted_money": [{"value": 100000, "currency": "EUR"}],
            "extracted_durations": [{"value": 30, "unit": "days"}],
            "extracted_milestones": [{"name": "Phase 1 Complete"}],
            "extracted_standards": [{"code": "ISO 9001"}],
            "extracted_penalties": [{"amount": 5000, "condition": "late delivery"}],
            "extracted_actors": [{"name": "Contractor", "role": "responsible"}],
            "extracted_materials": [{"name": "Steel", "quantity": 100}],
            "extracted_specs": [{"requirement": "Load capacity 10 tons"}],
            "extracted_entities": [],
            "extraction_confidence": 0.92,
        }

        # Verify key fields are accessible
        assert len(state["extracted_clauses"]) == 1
        assert "TIME" in state["clauses_by_category"]
        assert len(state["clauses_by_category"]) == 6
        assert state["extraction_confidence"] == 0.92


class TestGraphStateCoherenceFields:
    """Tests for GraphState coherence fields - TS-I13-STATE-001-09"""

    def test_graph_state_coherence_fields(self) -> None:
        """
        TS-I13-STATE-001-09: GraphState accepts coherence fields.

        Fields: coherence_alerts, alerts_by_category, coherence_subscores,
                coherence_score, category_weights, coherence_methodology_version
        """
        from src.core.ai.orchestration.state import GraphState

        # Create a valid GraphState with coherence fields
        state: GraphState = {
            "coherence_alerts": [
                {"type": "Schedule Mismatch", "severity": "Critical"}
            ],
            "alerts_by_category": {
                "TIME": [{"type": "Schedule Mismatch"}],
                "BUDGET": [],
                "SCOPE": [],
                "QUALITY": [],
                "TECHNICAL": [],
                "LEGAL": [],
            },
            "coherence_subscores": {
                "SCOPE": 0.80,
                "BUDGET": 0.62,
                "QUALITY": 0.85,
                "TECHNICAL": 0.72,
                "LEGAL": 0.90,
                "TIME": 0.75,
            },
            "coherence_score": 0.77,
            "category_weights": {
                "SCOPE": 0.20,
                "BUDGET": 0.20,
                "QUALITY": 0.15,
                "TECHNICAL": 0.15,
                "LEGAL": 0.15,
                "TIME": 0.15,
            },
            "coherence_methodology_version": "2.0",
        }

        # Verify fields are accessible
        assert len(state["coherence_alerts"]) == 1
        assert len(state["alerts_by_category"]) == 6
        assert len(state["coherence_subscores"]) == 6
        assert state["coherence_score"] == 0.77
        assert state["coherence_methodology_version"] == "2.0"


class TestGraphStateHITLFields:
    """Tests for GraphState HITL fields - TS-I13-STATE-001-10"""

    def test_graph_state_hitl_fields(self) -> None:
        """
        TS-I13-STATE-001-10: GraphState accepts HITL fields.

        Fields: hitl_status, hitl_item_id, hitl_required_reason,
                hitl_approved_by, hitl_approved_at
        """
        from src.core.ai.orchestration.state import GraphState, HITLStatus

        # Create a valid GraphState with HITL fields
        state: GraphState = {
            "hitl_status": HITLStatus.PENDING,
            "hitl_item_id": "review-item-123",
            "hitl_required_reason": "low_confidence",
            "hitl_approved_by": None,
            "hitl_approved_at": None,
        }

        # Verify fields are accessible
        assert state["hitl_status"] == HITLStatus.PENDING
        assert state["hitl_item_id"] == "review-item-123"
        assert state["hitl_required_reason"] == "low_confidence"
        assert state["hitl_approved_by"] is None

        # Test approved state
        state["hitl_status"] = HITLStatus.APPROVED
        state["hitl_approved_by"] = "John Reviewer"
        state["hitl_approved_at"] = "2026-02-15T10:30:00Z"

        assert state["hitl_status"] == HITLStatus.APPROVED
        assert state["hitl_approved_by"] == "John Reviewer"


class TestGraphStateOptionalFields:
    """Tests for GraphState optional fields - TS-I13-STATE-001-11"""

    def test_graph_state_optional_fields(self) -> None:
        """
        TS-I13-STATE-001-11: All GraphState fields are optional (total=False).

        An empty GraphState dict should be valid.
        Partial state with only some fields should be valid.
        """
        from src.core.ai.orchestration.state import GraphState

        # Empty state should be valid
        empty_state: GraphState = {}
        assert isinstance(empty_state, dict)

        # Partial state should be valid
        partial_state: GraphState = {
            "run_id": "run-123",
            "coherence_score": 0.85,
        }
        assert partial_state["run_id"] == "run-123"
        assert partial_state["coherence_score"] == 0.85

        # Missing fields should not raise KeyError on .get()
        assert partial_state.get("tenant_id") is None
        assert partial_state.get("extracted_clauses") is None


class TestGraphStateSerialization:
    """Tests for GraphState serialization - TS-I13-STATE-001-12"""

    def test_graph_state_serializable(self) -> None:
        """
        TS-I13-STATE-001-12: GraphState can be JSON serialized.

        All fields except document_bytes should be JSON serializable.
        This is required for checkpointing and LangSmith tracing.
        """
        from src.core.ai.orchestration.state import (
            GraphState,
            IntentType,
            HITLStatus,
        )

        # Create a state with various field types
        state: GraphState = {
            "run_id": "run-123",
            "tenant_id": "tenant-456",
            "project_id": "project-789",
            "query": "Analyze contract",
            "intent": IntentType.DOCUMENT,
            "intent_confidence": 0.95,
            "intent_metadata": {"source": "user_input"},
            "coherence_subscores": {
                "SCOPE": 0.80,
                "BUDGET": 0.62,
                "QUALITY": 0.85,
                "TECHNICAL": 0.72,
                "LEGAL": 0.90,
                "TIME": 0.75,
            },
            "coherence_score": 0.77,
            "hitl_status": HITLStatus.NOT_REQUIRED,
            "errors": [],
            "execution_path": ["intent_classifier", "document_ingestion"],
        }

        # Prepare state for serialization (convert enums to values)
        serializable_state = {
            k: (v.value if hasattr(v, "value") else v)
            for k, v in state.items()
        }

        # Should serialize without error
        json_str = json.dumps(serializable_state)
        assert isinstance(json_str, str)

        # Should deserialize back
        deserialized = json.loads(json_str)
        assert deserialized["run_id"] == "run-123"
        assert deserialized["coherence_score"] == 0.77
        assert deserialized["intent"] == "document"
