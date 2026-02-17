"""
TS-I13-EDGE-001: Conditional Edges Unit Tests

TDD Red Phase - These tests define the routing logic contracts.

Test Suite ID: TS-I13-EDGE-001
Total Tests: 14
Priority: P0 (Critical)

Aligned with: PLAN_LANGGRAPH_TDD_TESTPLAN_I13_2026-02-15.md
"""

from __future__ import annotations

import pytest

from src.core.ai.orchestration.state import (
    CoherenceCategory,
    GraphState,
    HITLStatus,
    IntentType,
)


class TestRouteByIntentDocument:
    """Tests for routing by DOCUMENT intent - TS-I13-EDGE-001-01"""

    def test_route_by_intent_document(self) -> None:
        """
        TS-I13-EDGE-001-01: intent=DOCUMENT routes to "document_ingestion".

        When the classified intent is DOCUMENT, the router should
        direct the flow to the document_ingestion node.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with DOCUMENT intent and sufficient confidence
        state: GraphState = {
            "intent": IntentType.DOCUMENT,
            "intent_confidence": 0.85,
        }

        # Route should return "document_ingestion"
        result = route_by_intent(state)
        assert result == "document_ingestion", (
            f"Expected 'document_ingestion' for DOCUMENT intent, got '{result}'"
        )


class TestRouteByIntentProject:
    """Tests for routing by PROJECT intent - TS-I13-EDGE-001-02"""

    def test_route_by_intent_project(self) -> None:
        """
        TS-I13-EDGE-001-02: intent=PROJECT routes to "wbs_generator".

        When the classified intent is PROJECT, the router should
        direct the flow to the wbs_generator node.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with PROJECT intent and sufficient confidence
        state: GraphState = {
            "intent": IntentType.PROJECT,
            "intent_confidence": 0.85,
        }

        # Route should return "wbs_generator"
        result = route_by_intent(state)
        assert result == "wbs_generator", (
            f"Expected 'wbs_generator' for PROJECT intent, got '{result}'"
        )


class TestRouteByIntentStakeholder:
    """Tests for routing by STAKEHOLDER intent - TS-I13-EDGE-001-03"""

    def test_route_by_intent_stakeholder(self) -> None:
        """
        TS-I13-EDGE-001-03: intent=STAKEHOLDER routes to "stakeholder_extractor".

        When the classified intent is STAKEHOLDER, the router should
        direct the flow to the stakeholder_extractor node.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with STAKEHOLDER intent and sufficient confidence
        state: GraphState = {
            "intent": IntentType.STAKEHOLDER,
            "intent_confidence": 0.85,
        }

        # Route should return "stakeholder_extractor"
        result = route_by_intent(state)
        assert result == "stakeholder_extractor", (
            f"Expected 'stakeholder_extractor' for STAKEHOLDER intent, got '{result}'"
        )


class TestRouteByIntentProcurement:
    """Tests for routing by PROCUREMENT intent - TS-I13-EDGE-001-04"""

    def test_route_by_intent_procurement(self) -> None:
        """
        TS-I13-EDGE-001-04: intent=PROCUREMENT routes to "procurement_planner".

        When the classified intent is PROCUREMENT, the router should
        direct the flow to the procurement_planner node.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with PROCUREMENT intent and sufficient confidence
        state: GraphState = {
            "intent": IntentType.PROCUREMENT,
            "intent_confidence": 0.85,
        }

        # Route should return "procurement_planner"
        result = route_by_intent(state)
        assert result == "procurement_planner", (
            f"Expected 'procurement_planner' for PROCUREMENT intent, got '{result}'"
        )


class TestRouteByIntentAnalysis:
    """Tests for routing by ANALYSIS intent - TS-I13-EDGE-001-05"""

    def test_route_by_intent_analysis(self) -> None:
        """
        TS-I13-EDGE-001-05: intent=ANALYSIS routes to "evidence_retriever".

        When the classified intent is ANALYSIS, the router should
        direct the flow to the evidence_retriever node.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with ANALYSIS intent and sufficient confidence
        state: GraphState = {
            "intent": IntentType.ANALYSIS,
            "intent_confidence": 0.85,
        }

        # Route should return "evidence_retriever"
        result = route_by_intent(state)
        assert result == "evidence_retriever", (
            f"Expected 'evidence_retriever' for ANALYSIS intent, got '{result}'"
        )


class TestRouteByIntentCoherence:
    """Tests for routing by COHERENCE intent - TS-I13-EDGE-001-06"""

    def test_route_by_intent_coherence(self) -> None:
        """
        TS-I13-EDGE-001-06: intent=COHERENCE routes to "coherence_evaluator".

        When the classified intent is COHERENCE, the router should
        direct the flow to the coherence_evaluator node.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with COHERENCE intent and sufficient confidence
        state: GraphState = {
            "intent": IntentType.COHERENCE,
            "intent_confidence": 0.85,
        }

        # Route should return "coherence_evaluator"
        result = route_by_intent(state)
        assert result == "coherence_evaluator", (
            f"Expected 'coherence_evaluator' for COHERENCE intent, got '{result}'"
        )


class TestRouteByIntentUnknown:
    """Tests for routing by UNKNOWN intent - TS-I13-EDGE-001-07"""

    def test_route_by_intent_unknown(self) -> None:
        """
        TS-I13-EDGE-001-07: intent=UNKNOWN routes to "error_handler".

        When the classified intent is UNKNOWN, the router should
        direct the flow to the error_handler node for graceful handling.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Create state with UNKNOWN intent
        state: GraphState = {
            "intent": IntentType.UNKNOWN,
            "intent_confidence": 0.30,
        }

        # Route should return "error_handler"
        result = route_by_intent(state)
        assert result == "error_handler", (
            f"Expected 'error_handler' for UNKNOWN intent, got '{result}'"
        )


class TestRouteByIntentLowConfidence:
    """Tests for routing with low confidence - TS-I13-EDGE-001-08"""

    def test_route_by_intent_low_confidence(self) -> None:
        """
        TS-I13-EDGE-001-08: confidence < 0.5 routes to "error_handler" regardless of intent.

        When the intent classification confidence is below the threshold (0.5),
        the router should direct to error_handler regardless of the classified intent.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_intent

        # Test with DOCUMENT intent but low confidence
        state: GraphState = {
            "intent": IntentType.DOCUMENT,
            "intent_confidence": 0.40,
        }

        # Should return "error_handler" due to low confidence, NOT "document_ingestion"
        result = route_by_intent(state)
        assert result == "error_handler", (
            f"Expected 'error_handler' for low confidence (0.40), got '{result}'"
        )

        # Test with PROJECT intent but low confidence
        state2: GraphState = {
            "intent": IntentType.PROJECT,
            "intent_confidence": 0.25,
        }

        result2 = route_by_intent(state2)
        assert result2 == "error_handler", (
            f"Expected 'error_handler' for low confidence (0.25), got '{result2}'"
        )

        # Test at exact threshold boundary (0.5 should pass, 0.49 should fail)
        state3: GraphState = {
            "intent": IntentType.ANALYSIS,
            "intent_confidence": 0.49,
        }

        result3 = route_by_intent(state3)
        assert result3 == "error_handler", (
            f"Expected 'error_handler' for confidence at 0.49, got '{result3}'"
        )


class TestRouteByEvidenceGateMet:
    """Tests for routing when evidence threshold is met - TS-I13-EDGE-001-09"""

    def test_route_by_evidence_gate_met(self) -> None:
        """
        TS-I13-EDGE-001-09: evidence_threshold_met=True → "coherence_evaluator".

        When the evidence retrieval threshold has been met, the router should
        direct the flow to the coherence_evaluator node for evaluation.

        Per PLAN_LANGGRAPH_ORCHESTRATION_I13 Section 4.1.
        """
        from src.core.ai.orchestration.edges import route_by_evidence_gate

        # Create state with evidence threshold met
        state: GraphState = {
            "evidence_threshold_met": True,
        }

        # Route should return "coherence_evaluator"
        result = route_by_evidence_gate(state)
        assert result == "coherence_evaluator", (
            f"Expected 'coherence_evaluator' when evidence_threshold_met=True, got '{result}'"
        )
