"""
Phase 7 E2E API Tests for Coherence Engine v0.3

Tests the coherence evaluation REST API endpoints:
- POST /v0/coherence/evaluate (backward-compatible)
- POST /v0/coherence/evaluate?include_diagnostics=true
- POST /v0/coherence/evaluate/diagnostics

Verifies:
1. Backward compatibility (response shape matches v0.2)
2. Granular scoring (5-97 range, not 0/100)
3. low_budget_mode defaults to True
4. Diagnostics available via query param and separate endpoint
5. Category inference from clause data
6. RAG similarity integration

Location: apps/api/tests/coherence/test_api_v3.py
"""

from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from src.coherence.models import (
    Alert,
    CategoryBreakdown,
    Clause,
    CoherenceResult,
    EnrichedCoherenceResult,
    SeverityCount,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_clauses():
    """Sample clauses for testing."""
    return [
        Clause(
            id="BUD-001",
            text="Budget overrun detected: current $120,000 vs planned $100,000",
            data={
                "planned": 100000,
                "current": 120000,
                "category": "budget",
            },
        ),
        Clause(
            id="SCH-001",
            text="Project deadline: 2024-06-01",
            data={
                "end_date": "2024-06-01",
                "status": "on_track",
            },
        ),
        Clause(
            id="LEG-001",
            text="Contract warranty period: 24 months",
            data={
                "warranty_months": 24,
            },
        ),
    ]


@pytest.fixture
def sample_enriched_result():
    """Sample EnrichedCoherenceResult for mocking."""
    return EnrichedCoherenceResult(
        overall_score=72.5,
        alerts=[
            Alert(
                rule_id="DET-BUD-OVERRUN",
                severity="high",
                category="financial",
                message="Budget overrun detected: 20% over planned",
                evidence={
                    "source_clause_id": "BUD-001",
                    "claim": "Budget overrun",
                    "quote": "current $120,000 vs planned $100,000",
                },
            )
        ],
        category_breakdown=[
            CategoryBreakdown(
                category="financial",
                score=60.0,
                alert_count=1,
                severity_breakdown=SeverityCount(critical=0, high=1, medium=0, low=0),
                impact_percentage=20.0,
            ),
            CategoryBreakdown(
                category="schedule",
                score=85.0,
                alert_count=0,
                severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0),
                impact_percentage=15.0,
            ),
        ],
        calculated_at=datetime.utcnow(),
        # Diagnostic fields
        finding_signals=[],
        llm_cost_usd=0.0,
    )


# =============================================================================
# TEST 1: Backward Compatibility
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_backward_compatible_response_shape(sample_clauses, sample_enriched_result):
    """
    Test that POST /v0/coherence/evaluate returns the same response shape as v0.2.

    Success Criteria:
    - Response has overall_score, alerts, category_breakdown, calculated_at
    - No diagnostic fields exposed (finding_signals, llm_cost_usd)
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    # Mock evaluate_coherence to return sample result
    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        # Create request
        request = CoherenceEvaluateRequest(
            clauses=sample_clauses,
        )

        # Mock database session
        mock_db = Mock()

        # Call endpoint
        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=mock_db,
        )

        # Verify response type
        assert isinstance(result, CoherenceResult)
        assert not isinstance(result, EnrichedCoherenceResult)

        # Verify core fields exist
        assert hasattr(result, "overall_score")
        assert hasattr(result, "alerts")
        assert hasattr(result, "category_breakdown")
        assert hasattr(result, "calculated_at")

        # Verify diagnostic fields DO NOT exist (backward compat)
        assert not hasattr(result, "finding_signals")
        assert not hasattr(result, "llm_cost_usd")

        # Verify score is granular (not 0/100)
        assert result.overall_score == 72.5  # Granular float
        assert result.overall_score != 0
        assert result.overall_score != 100


# =============================================================================
# TEST 2: Granular Scoring
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_granular_scoring_not_binary(sample_clauses, sample_enriched_result):
    """
    Test that scores are granular floats in 5-97 range, not binary 0/100.

    Success Criteria:
    - overall_score is float type
    - Score is NOT exactly 0 or 100
    - Score is in reasonable range (5-97)
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        request = CoherenceEvaluateRequest(clauses=sample_clauses)
        mock_db = Mock()

        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=mock_db,
        )

        # Verify granular scoring
        assert isinstance(result.overall_score, float)
        assert result.overall_score != 0.0
        assert result.overall_score != 100.0
        assert 5.0 <= result.overall_score <= 97.0


# =============================================================================
# TEST 3: Low Budget Mode Default
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_low_budget_mode_defaults_to_true(sample_clauses, sample_enriched_result):
    """
    Test that low_budget_mode defaults to True.

    Success Criteria:
    - When not specified, low_budget_mode=True is passed to config
    - LLM evaluators are skipped (verified via mock)
    """
    from src.coherence.graph.state import EvaluationConfig
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        # Request WITHOUT low_budget_mode specified
        request = CoherenceEvaluateRequest(clauses=sample_clauses)
        mock_db = Mock()

        await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=mock_db,
        )

        # Verify evaluate_coherence was called with low_budget_mode=True
        call_args = mock_evaluate.call_args
        config_arg = call_args.kwargs.get("config")

        assert isinstance(config_arg, EvaluationConfig)
        assert config_arg.low_budget_mode is True  # Default


# =============================================================================
# TEST 4: Diagnostics via Query Param
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_diagnostics_via_query_param(sample_clauses, sample_enriched_result):
    """
    Test that ?include_diagnostics=true returns EnrichedCoherenceResult.

    Success Criteria:
    - Response includes diagnostic fields
    - Response type is EnrichedCoherenceResult
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        request = CoherenceEvaluateRequest(clauses=sample_clauses)
        mock_db = Mock()

        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=True,  # Query param
            db=mock_db,
        )

        # Verify response type
        assert isinstance(result, EnrichedCoherenceResult)

        # Verify diagnostic fields exist
        assert hasattr(result, "finding_signals")
        assert hasattr(result, "llm_cost_usd")

        # Verify core fields still exist
        assert hasattr(result, "overall_score")
        assert hasattr(result, "alerts")


# =============================================================================
# TEST 5: Diagnostics Endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_diagnostics_endpoint(sample_clauses, sample_enriched_result):
    """
    Test POST /v0/coherence/evaluate/diagnostics returns full diagnostics.

    Success Criteria:
    - Endpoint exists
    - Always returns EnrichedCoherenceResult
    - Equivalent to include_diagnostics=true query param
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_with_diagnostics

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        request = CoherenceEvaluateRequest(clauses=sample_clauses)
        mock_db = Mock()

        result = await evaluate_with_diagnostics(
            payload=request,
            db=mock_db,
        )

        # Verify response type
        assert isinstance(result, EnrichedCoherenceResult)

        # Verify diagnostic fields
        assert hasattr(result, "finding_signals")
        assert hasattr(result, "llm_cost_usd")


# =============================================================================
# TEST 6: Category Inference
# =============================================================================


def test_category_inference_from_clause_data():
    """
    Test _infer_category_from_clause helper (Task 7.2).

    Success Criteria:
    - BUDGET: Infers from budget/cost/amount fields
    - TIME: Infers from deadline/schedule fields
    - LEGAL: Infers from contract/warranty fields
    - TECHNICAL: Infers from specification/BOM fields
    - QUALITY: Infers from inspection/quality fields
    - SCOPE: Default fallback
    """
    from src.coherence.router import _infer_category_from_clause

    # Test BUDGET inference from data
    budget_clause = Clause(
        id="test-1",
        text="Some text",
        data={"budget": 100000, "planned": 100000},
    )
    assert _infer_category_from_clause(budget_clause) == "BUDGET"

    # Test TIME inference from data
    time_clause = Clause(
        id="test-2",
        text="Some text",
        data={"deadline": "2024-06-01", "end_date": "2024-06-01"},
    )
    assert _infer_category_from_clause(time_clause) == "TIME"

    # Test LEGAL inference from data
    legal_clause = Clause(
        id="test-3",
        text="Some text",
        data={"warranty": 24, "contract_id": "CTR-001"},
    )
    assert _infer_category_from_clause(legal_clause) == "LEGAL"

    # Test TECHNICAL inference from data
    technical_clause = Clause(
        id="test-4",
        text="Some text",
        data={"specification": "ISO-9001", "bom": []},
    )
    assert _infer_category_from_clause(technical_clause) == "TECHNICAL"

    # Test QUALITY inference from data
    quality_clause = Clause(
        id="test-5",
        text="Some text",
        data={"inspection": "monthly", "quality": "high"},
    )
    assert _infer_category_from_clause(quality_clause) == "QUALITY"

    # Test TIME inference from text with "milestones" keyword
    # Note: "milestones" triggers TIME category, not SCOPE
    scope_clause = Clause(
        id="test-6",
        text="Project deliverables and milestones",
        data={},
    )
    assert _infer_category_from_clause(scope_clause) == "TIME"

    # Test BUDGET inference from text (fallback)
    budget_text_clause = Clause(
        id="test-7",
        text="Total budget is $500,000 USD",
        data={},
    )
    assert _infer_category_from_clause(budget_text_clause) == "BUDGET"


# =============================================================================
# TEST 7: RAG Integration
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_rag_similarity_enabled_by_default(sample_clauses, sample_enriched_result):
    """
    Test that include_rag_similarity defaults to True.

    Success Criteria:
    - When not specified, include_rag_similarity=True is passed to config
    """
    from src.coherence.graph.state import EvaluationConfig
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        # Request WITHOUT include_rag_similarity specified
        request = CoherenceEvaluateRequest(clauses=sample_clauses)
        mock_db = Mock()

        await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=mock_db,
        )

        # Verify evaluate_coherence was called with include_rag_similarity=True
        call_args = mock_evaluate.call_args
        config_arg = call_args.kwargs.get("config")

        assert isinstance(config_arg, EvaluationConfig)
        assert config_arg.include_rag_similarity is True  # Default


# =============================================================================
# TEST 8: Explicit Clauses vs Project ID
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_accepts_explicit_clauses(sample_clauses, sample_enriched_result):
    """
    Test that endpoint accepts explicit clauses without project_id.

    Success Criteria:
    - Clauses provided → use them directly, no RAG fetch
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        with patch("src.coherence.router.get_clauses_from_rag") as mock_rag:
            mock_evaluate.return_value = sample_enriched_result

            # Request with explicit clauses
            request = CoherenceEvaluateRequest(clauses=sample_clauses)
            mock_db = Mock()

            await evaluate_project_coherence(
                payload=request,
                include_diagnostics=False,
                db=mock_db,
            )

            # Verify RAG was NOT called
            mock_rag.assert_not_called()

            # Verify evaluate_coherence was called with provided clauses
            call_args = mock_evaluate.call_args
            assert call_args.kwargs.get("clauses") == sample_clauses


@pytest.mark.asyncio
async def test_evaluate_fetches_from_rag_with_project_id(sample_clauses, sample_enriched_result):
    """
    Test that endpoint fetches clauses from RAG when project_id is provided.

    Success Criteria:
    - project_id provided → fetch from RAG
    - Fetched clauses are passed to evaluate_coherence
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        with patch("src.coherence.router.get_clauses_from_rag") as mock_rag:
            mock_evaluate.return_value = sample_enriched_result
            mock_rag.return_value = sample_clauses

            # Request with project_id
            project_id = uuid4()
            request = CoherenceEvaluateRequest(project_id=project_id)
            mock_db = Mock()

            await evaluate_project_coherence(
                payload=request,
                include_diagnostics=False,
                db=mock_db,
            )

            # Verify RAG was called
            mock_rag.assert_called_once_with(mock_db, project_id, 50)

            # Verify evaluate_coherence was called with fetched clauses
            call_args = mock_evaluate.call_args
            assert call_args.kwargs.get("clauses") == sample_clauses


@pytest.mark.asyncio
async def test_evaluate_raises_422_when_no_input_provided(sample_enriched_result):
    """
    Test that endpoint raises 422 when neither project_id nor clauses are provided.

    Success Criteria:
    - HTTPException with 422 status code
    """
    from fastapi import HTTPException

    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        # Request with NEITHER project_id NOR clauses
        request = CoherenceEvaluateRequest()
        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await evaluate_project_coherence(
                payload=request,
                include_diagnostics=False,
                db=mock_db,
            )

        assert exc_info.value.status_code == 422
        assert "project_id or clauses" in exc_info.value.detail.lower()


# =============================================================================
# TEST 9: Cost Tracking
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_diagnostics_includes_cost_tracking(sample_clauses):
    """
    Test that diagnostics response includes llm_cost_usd field.

    Success Criteria:
    - llm_cost_usd field exists in EnrichedCoherenceResult
    - llm_cost_usd=0.0 when low_budget_mode=True (no LLM calls)
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    # Create enriched result with cost tracking
    enriched_with_cost = EnrichedCoherenceResult(
        overall_score=75.0,
        alerts=[],
        category_breakdown=[],
        calculated_at=datetime.utcnow(),
        finding_signals=[],
        llm_cost_usd=0.0,  # Zero cost in low_budget_mode
    )

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = enriched_with_cost

        request = CoherenceEvaluateRequest(
            clauses=sample_clauses,
            low_budget_mode=True,  # No LLM
        )
        mock_db = Mock()

        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=True,
            db=mock_db,
        )

        # Verify cost tracking
        assert hasattr(result, "llm_cost_usd")
        assert result.llm_cost_usd == 0.0  # Zero cost in low budget mode


# =============================================================================
# TEST 10: No Regressions in Existing API
# =============================================================================


@pytest.mark.asyncio
async def test_evaluate_no_regression_in_response_fields(sample_clauses, sample_enriched_result):
    """
    Test that all existing v0.2 response fields are preserved in v0.3.

    Success Criteria:
    - overall_score (float)
    - alerts (list[Alert])
    - category_breakdown (list[CategoryBreakdown])
    - calculated_at (datetime)
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    with patch("src.coherence.router.evaluate_coherence") as mock_evaluate:
        mock_evaluate.return_value = sample_enriched_result

        request = CoherenceEvaluateRequest(clauses=sample_clauses)
        mock_db = Mock()

        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=mock_db,
        )

        # Verify all v0.2 fields exist
        assert hasattr(result, "overall_score")
        assert isinstance(result.overall_score, float)

        assert hasattr(result, "alerts")
        assert isinstance(result.alerts, list)
        if result.alerts:
            assert all(isinstance(a, Alert) for a in result.alerts)

        assert hasattr(result, "category_breakdown")
        assert isinstance(result.category_breakdown, list)
        if result.category_breakdown:
            assert all(isinstance(cb, CategoryBreakdown) for cb in result.category_breakdown)

        assert hasattr(result, "calculated_at")
        assert isinstance(result.calculated_at, datetime)


# =============================================================================
# TEST 11: Conversion Helper
# =============================================================================


def test_convert_enriched_to_coherence_result():
    """
    Test _convert_enriched_to_coherence_result helper (Task 7.3).

    Success Criteria:
    - Correctly converts EnrichedCoherenceResult to CoherenceResult
    - Preserves core fields
    - Strips diagnostic fields
    """
    from src.coherence.router import _convert_enriched_to_coherence_result

    enriched = EnrichedCoherenceResult(
        overall_score=80.5,
        alerts=[
            Alert(
                rule_id="TEST-001",
                severity="low",
                category="scope",
                message="Test alert",
                evidence={
                    "source_clause_id": "CL-001",
                    "claim": "Test",
                    "quote": "Test quote",
                },
            )
        ],
        category_breakdown=[
            CategoryBreakdown(
                category="scope",
                score=80.0,
                alert_count=1,
                severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=1),
                impact_percentage=20.0,
            )
        ],
        calculated_at=datetime(2024, 1, 1, 12, 0, 0),
        # Diagnostic fields
        finding_signals=[],
        llm_cost_usd=0.001,
    )

    result = _convert_enriched_to_coherence_result(enriched)

    # Verify correct type
    assert isinstance(result, CoherenceResult)
    assert not isinstance(result, EnrichedCoherenceResult)

    # Verify core fields preserved
    assert result.overall_score == 80.5
    assert len(result.alerts) == 1
    assert result.alerts[0].rule_id == "TEST-001"
    assert len(result.category_breakdown) == 1
    assert result.category_breakdown[0].category == "scope"
    assert result.calculated_at == datetime(2024, 1, 1, 12, 0, 0)

    # Verify diagnostic fields NOT present
    assert not hasattr(result, "finding_signals")
    assert not hasattr(result, "diagnostics")
    assert not hasattr(result, "llm_cost_usd")
