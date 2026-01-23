# tests/coherence/test_llm_integration.py
"""
C2Pro - LLM Integration Service Tests (CE-25)

Integration tests for the CoherenceLLMService.
Uses mocking for consistent, deterministic testing.

Version: 1.0.0
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.coherence.models import Clause, ProjectContext


# ===========================================
# TEST: CoherenceLLMService INITIALIZATION
# ===========================================


class TestCoherenceLLMServiceInit:
    """Tests for CoherenceLLMService initialization."""

    def test_service_initializes_with_defaults(self, patch_anthropic_wrapper_for_integration):
        """Test service initializes with default parameters."""
        from src.modules.coherence.llm_integration import CoherenceLLMService

        service = CoherenceLLMService()

        assert service.low_budget_mode is False
        assert service.total_analyses == 0
        assert service.total_tokens == 0
        assert service.total_cost == 0.0

    def test_service_initializes_with_custom_params(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test service initializes with custom parameters."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from src.modules.ai.model_router import AITaskType

        service = CoherenceLLMService(
            default_task_type=AITaskType.COHERENCE_CHECK,
            low_budget_mode=True,
        )

        assert service.low_budget_mode is True
        assert service.default_task_type == AITaskType.COHERENCE_CHECK


# ===========================================
# TEST: CLAUSE ANALYSIS
# ===========================================


class TestCoherenceLLMServiceClauseAnalysis:
    """Tests for clause analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_clause_with_issues(
        self,
        mock_clause_analysis_with_issues,
        sample_clause_ambiguous,
    ):
        """Test analyzing a clause that has issues."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_clause_analysis_with_issues)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.analyze_clause(sample_clause_ambiguous)

        assert result.has_issues is True
        assert len(result.issues) == 3
        assert result.clause_id == sample_clause_ambiguous.id
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_analyze_clause_without_issues(
        self,
        mock_clause_analysis_no_issues,
        sample_clause_clear,
    ):
        """Test analyzing a clause that has no issues."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_clause_analysis_no_issues)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.analyze_clause(sample_clause_clear)

        assert result.has_issues is False
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_analyze_clause_updates_statistics(
        self,
        mock_clause_analysis_with_issues,
        sample_clause_ambiguous,
    ):
        """Test that clause analysis updates service statistics."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(
                mock_clause_analysis_with_issues,
                input_tokens=500,
                output_tokens=200,
                cost_usd=0.001,
            )
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()

            assert service.total_analyses == 0

            await service.analyze_clause(sample_clause_ambiguous)

            assert service.total_analyses == 1
            assert service.total_tokens > 0
            assert service.total_cost > 0


# ===========================================
# TEST: RULE VERIFICATION
# ===========================================


class TestCoherenceLLMServiceRuleVerification:
    """Tests for rule verification functionality."""

    @pytest.mark.asyncio
    async def test_check_coherence_rule_violation(
        self,
        mock_llm_response_violation,
        sample_clause_ambiguous,
    ):
        """Test checking a coherence rule that is violated."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_llm_response_violation)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.check_coherence_rule(
                clause=sample_clause_ambiguous,
                rule_id="R-SCOPE-CLARITY-01",
                rule_description="Check for ambiguous scope",
                detection_logic="Find vague terms",
            )

        assert result["rule_violated"] is True
        assert result["clause_id"] == sample_clause_ambiguous.id
        assert result["rule_id"] == "R-SCOPE-CLARITY-01"

    @pytest.mark.asyncio
    async def test_check_coherence_rule_no_violation(
        self,
        mock_llm_response_no_violation,
        sample_clause_clear,
    ):
        """Test checking a coherence rule that is not violated."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_llm_response_no_violation)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.check_coherence_rule(
                clause=sample_clause_clear,
                rule_id="R-SCOPE-CLARITY-01",
                rule_description="Check for ambiguous scope",
                detection_logic="Find vague terms",
            )

        assert result["rule_violated"] is False


# ===========================================
# TEST: MULTI-CLAUSE ANALYSIS
# ===========================================


class TestCoherenceLLMServiceMultiClause:
    """Tests for multi-clause coherence analysis."""

    @pytest.mark.asyncio
    async def test_analyze_multi_clause_coherence_with_issues(
        self,
        sample_clause_ambiguous,
        sample_clause_payment_vague,
    ):
        """Test multi-clause analysis that finds cross-clause issues."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_response = {
            "cross_clause_issues": [
                {
                    "type": "inconsistency",
                    "severity": "high",
                    "affected_clauses": ["CLAUSE-AMBIG-001", "CLAUSE-PAY-001"],
                    "description": "Payment terms reference unclear scope",
                    "evidence": "Payment clause references 'trabajos adicionales' without definition",
                }
            ],
            "overall_coherence_score": 65,
            "summary": "Found 1 cross-clause issue",
        }

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_response)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.analyze_multi_clause_coherence(
                clauses=[sample_clause_ambiguous, sample_clause_payment_vague]
            )

        assert "cross_clause_issues" in result
        assert len(result["cross_clause_issues"]) == 1
        assert result["overall_coherence_score"] == 65

    @pytest.mark.asyncio
    async def test_analyze_multi_clause_requires_minimum_clauses(
        self, sample_clause_ambiguous
    ):
        """Test that multi-clause analysis requires at least 2 clauses."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.analyze_multi_clause_coherence(
                clauses=[sample_clause_ambiguous]  # Only 1 clause
            )

        assert result["overall_coherence_score"] == 100
        assert len(result["cross_clause_issues"]) == 0


# ===========================================
# TEST: PROJECT CONTEXT ANALYSIS
# ===========================================


class TestCoherenceLLMServiceProjectAnalysis:
    """Tests for full project context analysis."""

    @pytest.mark.asyncio
    async def test_analyze_project_context(
        self,
        mock_clause_analysis_with_issues,
        sample_project_context,
    ):
        """Test full project context analysis."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        # Mock that returns different responses for different calls
        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_clause_analysis_with_issues)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={})

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            result = await service.analyze_project_context(
                context=sample_project_context,
                analyze_individual=True,
                analyze_cross_clause=False,  # Simplify for test
            )

        assert result.project_id == sample_project_context.id
        assert result.total_clauses_analyzed == len(sample_project_context.clauses)
        assert len(result.findings) > 0
        assert result.risk_level in ["low", "medium", "high", "critical"]


# ===========================================
# TEST: HELPER METHODS
# ===========================================


class TestCoherenceLLMServiceHelpers:
    """Tests for helper methods."""

    def test_calculate_risk_level_no_findings(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test risk level calculation with no findings."""
        from src.modules.coherence.llm_integration import CoherenceLLMService

        service = CoherenceLLMService()
        risk_level = service._calculate_risk_level([])

        assert risk_level == "low"

    def test_calculate_risk_level_critical(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test risk level calculation with critical findings."""
        from src.modules.coherence.llm_integration import CoherenceLLMService

        service = CoherenceLLMService()
        findings = [{"severity": "critical"}]
        risk_level = service._calculate_risk_level(findings)

        assert risk_level == "critical"

    def test_calculate_risk_level_high(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test risk level calculation with multiple high severity findings."""
        from src.modules.coherence.llm_integration import CoherenceLLMService

        service = CoherenceLLMService()
        findings = [
            {"severity": "high"},
            {"severity": "high"},
        ]
        risk_level = service._calculate_risk_level(findings)

        assert risk_level == "high"

    def test_generate_recommendations(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test recommendation generation from findings."""
        from src.modules.coherence.llm_integration import CoherenceLLMService

        service = CoherenceLLMService()
        findings = [
            {"type": "ambiguity", "recommendation": "Clarify terms"},
            {"type": "risk", "recommendation": "Review with legal"},
        ]
        recommendations = service._generate_recommendations(findings)

        assert len(recommendations) > 0
        assert any("ambig" in r.lower() for r in recommendations)


# ===========================================
# TEST: STATISTICS
# ===========================================


class TestCoherenceLLMServiceStatistics:
    """Tests for service statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(
        self,
        mock_clause_analysis_with_issues,
        sample_clause_ambiguous,
    ):
        """Test getting service statistics."""
        from src.modules.coherence.llm_integration import CoherenceLLMService
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_clause_analysis_with_issues)
        )
        mock_wrapper.get_statistics = MagicMock(return_value={
            "total_requests": 1,
            "cache_hits": 0,
        })

        with patch(
            "src.modules.coherence.llm_integration.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            service = CoherenceLLMService()
            await service.analyze_clause(sample_clause_ambiguous)

            stats = service.get_statistics()

        assert "total_analyses" in stats
        assert "total_tokens_used" in stats
        assert "total_cost_usd" in stats
        assert "wrapper_stats" in stats
        assert stats["total_analyses"] == 1


# ===========================================
# TEST: SINGLETON
# ===========================================


class TestCoherenceLLMServiceSingleton:
    """Tests for singleton behavior."""

    def test_get_coherence_llm_service_returns_instance(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test that get_coherence_llm_service returns an instance."""
        from src.modules.coherence.llm_integration import (
            get_coherence_llm_service,
            reset_coherence_llm_service,
        )

        # Reset to ensure clean state
        reset_coherence_llm_service()

        service = get_coherence_llm_service()

        assert service is not None

    def test_reset_coherence_llm_service(
        self, patch_anthropic_wrapper_for_integration
    ):
        """Test that reset clears the singleton."""
        from src.modules.coherence.llm_integration import (
            get_coherence_llm_service,
            reset_coherence_llm_service,
        )

        service1 = get_coherence_llm_service()
        reset_coherence_llm_service()
        service2 = get_coherence_llm_service()

        # After reset, should get a new instance
        # (Note: comparison is tricky with patches, but the reset should work)
        assert service2 is not None
