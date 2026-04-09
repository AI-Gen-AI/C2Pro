"""
Unit tests for coherence_scorer_node.

Tests that the coherence scorer properly derives compliance flags
from extracted risks and passes them to the coherence calculation service.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def base_state():
    """Base state with minimal required fields."""
    return {
        "project_id": str(uuid4()),
        "extracted_risks": [],
        "extracted_wbs": [],
        "bom_items": [],
        "messages": [],
        # Quality gate fields - set to pass by default
        "confidence_score": 0.85,
        "document_text": "This is a proper contract document with sufficient content to pass the quality gate threshold for coherence analysis testing purposes.",
    }


@pytest.fixture
def mock_coherence_service():
    """Mock the CoherenceCalculationService."""
    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 85
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_coherence_scorer_with_no_risks_and_wbs_returns_high_score(base_state):
    """No risks + WBS items = high score (all flags True)."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 100
        mock_result.category_scores = {
            MagicMock(value="SCOPE"): 100,
            MagicMock(value="BUDGET"): 100,
            MagicMock(value="TIME"): 100,
            MagicMock(value="TECHNICAL"): 100,
            MagicMock(value="LEGAL"): 100,
            MagicMock(value="QUALITY"): 100,
        }
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        # Verify all flags were True (no violations)
        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["scope_defined"] is True
        assert call_kwargs["schedule_within_contract"] is True
        assert call_kwargs["technical_consistent"] is True
        assert call_kwargs["legal_compliant"] is True
        assert call_kwargs["quality_standard_met"] is True


@pytest.mark.asyncio
async def test_coherence_scorer_with_legal_high_risk_sets_legal_false(base_state):
    """HIGH LEGAL risk → legal_compliant=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "LEGAL", "impact": "HIGH", "title": "Contract violation risk"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 95
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["legal_compliant"] is False
        # Other flags should still be True
        assert call_kwargs["scope_defined"] is True
        assert call_kwargs["schedule_within_contract"] is True
        assert call_kwargs["technical_consistent"] is True
        assert call_kwargs["quality_standard_met"] is True


@pytest.mark.asyncio
async def test_coherence_scorer_with_schedule_high_risk_sets_schedule_false(base_state):
    """HIGH SCHEDULE risk → schedule_within_contract=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "SCHEDULE", "impact": "HIGH", "title": "Delay risk"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 95
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["schedule_within_contract"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_with_time_critical_risk_sets_schedule_false(base_state):
    """CRITICAL TIME risk → schedule_within_contract=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "TIME", "impact": "CRITICAL", "title": "Timeline overrun"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 95
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["schedule_within_contract"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_with_technical_high_risk_sets_technical_false(base_state):
    """HIGH TECHNICAL risk → technical_consistent=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "TECHNICAL", "impact": "HIGH", "title": "Spec mismatch"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 95
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["technical_consistent"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_with_quality_high_risk_sets_quality_false(base_state):
    """HIGH QUALITY risk → quality_standard_met=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "QUALITY", "impact": "HIGH", "title": "ISO non-compliance"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 95
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["quality_standard_met"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_with_scope_high_risk_sets_scope_false(base_state):
    """HIGH SCOPE risk → scope_defined=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "SCOPE", "impact": "HIGH", "title": "Scope creep"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["scope_defined"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_with_budget_high_risk_marks_bom_unassigned(base_state):
    """HIGH BUDGET risk → BOM items marked as unassigned."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "FINANCIAL", "impact": "HIGH", "title": "Cost overrun"}
    ]
    base_state["bom_items"] = [
        {"name": "Item 1", "amount": 1000, "budget_line_assigned": True}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        # BOM items should be marked as unassigned
        assert len(call_kwargs["bom_items"]) == 1
        assert call_kwargs["bom_items"][0]["budget_line_assigned"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_no_wbs_no_risks_sets_scope_false(base_state):
    """No WBS and no risks → scope_defined=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    # Empty state - no WBS, no risks
    base_state["extracted_wbs"] = []
    base_state["extracted_risks"] = []

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["scope_defined"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_multiple_high_risks(base_state):
    """Multiple HIGH risks in different categories → multiple flags False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "LEGAL", "impact": "HIGH", "title": "Contract issue"},
        {"category": "SCHEDULE", "impact": "CRITICAL", "title": "Delay"},
        {"category": "TECHNICAL", "impact": "HIGH", "title": "Tech gap"},
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        assert call_kwargs["legal_compliant"] is False
        assert call_kwargs["schedule_within_contract"] is False
        assert call_kwargs["technical_consistent"] is False
        # These should still be True
        assert call_kwargs["scope_defined"] is True
        assert call_kwargs["quality_standard_met"] is True


@pytest.mark.asyncio
async def test_coherence_scorer_medium_risk_does_not_trigger(base_state):
    """MEDIUM risk should NOT set flag to False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["extracted_risks"] = [
        {"category": "LEGAL", "impact": "MEDIUM", "title": "Minor legal note"}
    ]

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 100
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        # MEDIUM should not trigger violation
        assert call_kwargs["legal_compliant"] is True


@pytest.mark.asyncio
async def test_coherence_scorer_missing_project_id_returns_zero(base_state):
    """Missing project_id returns score=0."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["project_id"] = None

    result = await coherence_scorer_node(base_state)

    assert result["coherence_score"] == 0
    assert result["coherence_breakdown"] == {}


@pytest.mark.asyncio
async def test_coherence_scorer_low_confidence_sets_scope_false(base_state):
    """Low confidence score → scope_defined=False (quality gate)."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.3}]
    base_state["confidence_score"] = 0.34  # Below 0.5 threshold
    base_state["document_text"] = "This is a real document with enough content to pass length check but low confidence."

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        # Low confidence should trigger scope_defined=False
        assert call_kwargs["scope_defined"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_short_document_sets_scope_false(base_state):
    """Very short document → scope_defined=False (quality gate)."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [{"code": "1.0", "name": "Task 1", "confidence": 0.9}]
    base_state["confidence_score"] = 0.9  # Good confidence
    base_state["document_text"] = "string"  # Too short (< 100 chars)

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        # Short document should trigger scope_defined=False
        assert call_kwargs["scope_defined"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_low_wbs_confidence_sets_scope_false(base_state):
    """WBS items with low average confidence → scope_defined=False."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [
        {"code": "1.0", "name": "Task 1", "confidence": 0.2},
        {"code": "1.1", "name": "Task 2", "confidence": 0.3},
        {"code": "1.2", "name": "Task 3", "confidence": 0.4},
    ]
    base_state["confidence_score"] = 0.6  # Above threshold
    base_state["document_text"] = "This is a proper document with enough content to analyze properly for the coherence scoring system."

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 70
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        # Low WBS confidence average (0.3) should trigger scope_defined=False
        assert call_kwargs["scope_defined"] is False


@pytest.mark.asyncio
async def test_coherence_scorer_good_quality_passes(base_state):
    """Good confidence + meaningful document → scope_defined=True."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    base_state["extracted_wbs"] = [
        {"code": "1.0", "name": "Task 1", "confidence": 0.85},
        {"code": "1.1", "name": "Task 2", "confidence": 0.9},
    ]
    base_state["confidence_score"] = 0.85
    base_state["document_text"] = "This is a proper contract document with all the necessary clauses and specifications required for a comprehensive analysis."

    with patch(
        "src.coherence.application.dependencies.build_coherence_calculation_service"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.global_score = 100
        mock_result.category_scores = {}
        mock_instance.calculate_coherence.return_value = mock_result
        mock_cls.return_value = mock_instance

        await coherence_scorer_node(base_state)

        call_kwargs = mock_instance.calculate_coherence.call_args[1]
        # Good quality should pass
        assert call_kwargs["scope_defined"] is True
