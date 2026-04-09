"""
test_llm_evaluator_v3.py — Tests for LLM Evaluator v0.3 Updates

Tests for Phase 4 LLM Evaluator features:
- Continuous scoring with impact_score (0.0-1.0)
- FindingSignal output
- JSON parsing with error handling
- Cost tracking (total_cost_usd, llm_calls_count)
- Graceful fallback on parse errors

Location: apps/api/tests/coherence/test_llm_evaluator_v3.py
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.coherence.models import Clause, FindingSignal
from src.coherence.rules_engine.llm_evaluator import (
    LlmEvaluationMetrics,
    LlmRuleEvaluator,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_wrapper():
    """Mock the Anthropic wrapper."""
    with patch("src.coherence.rules_engine.llm_evaluator.get_anthropic_wrapper") as mock:
        wrapper = MagicMock()
        mock.return_value = wrapper
        yield wrapper


@pytest.fixture
def evaluator(mock_wrapper) -> LlmRuleEvaluator:
    """Create a test evaluator with mocked wrapper."""
    return LlmRuleEvaluator(
        rule_id="R-TEST-001",
        rule_name="Test Rule",
        rule_description="A test rule for validation",
        detection_logic="Check for test patterns",
        default_severity="medium",
        category="scope",
    )


@pytest.fixture
def sample_clause() -> Clause:
    """Sample clause for testing."""
    return Clause(
        id="C1",
        text="The contractor shall perform work as necessary and appropriate.",
        data={"category": "scope"},
    )


def make_llm_response(content: str, cost: float = 0.001, cached: bool = False):
    """Helper to create mock LLM response."""
    response = MagicMock()
    response.content = content
    response.cost_usd = cost
    response.cached = cached
    response.model_used = "claude-3-haiku"
    return response


# =============================================================================
# TEST: LlmEvaluationMetrics
# =============================================================================


class TestLlmEvaluationMetrics:
    """Tests for the LlmEvaluationMetrics dataclass."""

    def test_initial_state(self):
        """Metrics should start at zero."""
        metrics = LlmEvaluationMetrics()
        assert metrics.total_cost_usd == 0.0
        assert metrics.llm_calls_count == 0
        assert metrics.cache_hits == 0
        assert metrics.evaluations_count == 0
        assert metrics.violations_found == 0

    def test_record_evaluation_with_violation(self):
        """Recording an evaluation with violation updates metrics."""
        metrics = LlmEvaluationMetrics()
        metrics.record_evaluation(
            cost=0.001,
            cached=False,
            impact_score=0.75,
            confidence=0.90,
        )

        assert metrics.evaluations_count == 1
        assert metrics.llm_calls_count == 1
        assert metrics.violations_found == 1
        assert metrics.total_cost_usd == 0.001
        assert metrics.avg_impact_score == 0.75
        assert metrics.avg_confidence == 0.90

    def test_record_cached_evaluation(self):
        """Cached evaluations don't increase cost or call count."""
        metrics = LlmEvaluationMetrics()
        metrics.record_evaluation(
            cost=0.001,
            cached=True,
            impact_score=0.50,
            confidence=0.80,
        )

        assert metrics.evaluations_count == 1
        assert metrics.llm_calls_count == 0
        assert metrics.cache_hits == 1
        assert metrics.total_cost_usd == 0.0  # No cost for cached

    def test_record_no_violation(self):
        """No violation means impact_score is None."""
        metrics = LlmEvaluationMetrics()
        metrics.record_evaluation(
            cost=0.001,
            cached=False,
            impact_score=None,
            confidence=None,
        )

        assert metrics.evaluations_count == 1
        assert metrics.violations_found == 0
        assert metrics.avg_impact_score == 0.0

    def test_violation_rate(self):
        """Violation rate calculated correctly."""
        metrics = LlmEvaluationMetrics()
        metrics.record_evaluation(0.001, False, 0.5, 0.9)
        metrics.record_evaluation(0.001, False, None, None)
        metrics.record_evaluation(0.001, False, 0.7, 0.8)

        assert metrics.evaluations_count == 3
        assert metrics.violations_found == 2
        assert metrics.violation_rate == pytest.approx(0.667, abs=0.01)

    def test_cache_hit_rate(self):
        """Cache hit rate calculated correctly."""
        metrics = LlmEvaluationMetrics()
        metrics.record_evaluation(0.001, False, 0.5, 0.9)
        metrics.record_evaluation(0.0, True, 0.5, 0.9)
        metrics.record_evaluation(0.001, False, 0.5, 0.9)
        metrics.record_evaluation(0.0, True, 0.5, 0.9)

        assert metrics.cache_hit_rate == 0.5

    def test_to_dict(self):
        """to_dict exports all metrics."""
        metrics = LlmEvaluationMetrics()
        metrics.record_evaluation(0.001, False, 0.75, 0.90)

        d = metrics.to_dict()

        assert "total_cost_usd" in d
        assert "llm_calls_count" in d
        assert "cache_hits" in d
        assert "evaluations_count" in d
        assert "violations_found" in d
        assert "violation_rate" in d
        assert "avg_impact_score" in d
        assert "avg_confidence" in d

    def test_record_parse_error(self):
        """Parse errors are tracked."""
        metrics = LlmEvaluationMetrics()
        metrics.record_parse_error()
        metrics.record_parse_error()

        assert metrics.parse_errors == 2


# =============================================================================
# TEST: JSON PARSING
# =============================================================================


class TestJsonParsing:
    """Tests for LLM response JSON parsing."""

    def test_parse_valid_json(self, evaluator):
        """Valid JSON is parsed correctly."""
        content = json.dumps({
            "impact_score": 0.75,
            "confidence": 0.90,
            "rule_violated": True,
            "evidence": {
                "quote": "as necessary",
                "explanation": "Ambiguous term found"
            },
            "recommendation": "Be more specific"
        })

        result = evaluator._parse_v3_response(content)

        assert result["impact_score"] == 0.75
        assert result["confidence"] == 0.90
        assert result["evidence"]["quote"] == "as necessary"

    def test_parse_json_in_markdown_block(self, evaluator):
        """JSON inside markdown code block is extracted."""
        content = """Here's my analysis:
```json
{
    "impact_score": 0.60,
    "confidence": 0.85,
    "rule_violated": true,
    "evidence": {"quote": "test", "explanation": "reason"},
    "recommendation": "fix it"
}
```
"""
        result = evaluator._parse_v3_response(content)

        assert result["impact_score"] == 0.60
        assert result["confidence"] == 0.85

    def test_parse_json_in_generic_code_block(self, evaluator):
        """JSON inside generic code block is extracted."""
        content = """```
{"impact_score": 0.50, "confidence": 0.75}
```"""
        result = evaluator._parse_v3_response(content)

        assert result["impact_score"] == 0.50

    def test_parse_malformed_json_recovers_partial(self, evaluator):
        """Malformed JSON attempts partial recovery."""
        content = """{"impact_score": 0.80, "confidence": 0.70, broken"""

        result = evaluator._parse_v3_response(content)

        # Should recover impact_score and confidence
        assert result["impact_score"] == 0.80
        assert result["confidence"] == 0.70
        assert result.get("parse_error") is True

    def test_parse_completely_invalid_returns_safe_default(self, evaluator):
        """Completely invalid content returns safe defaults."""
        content = "This is not JSON at all, just plain text."

        result = evaluator._parse_v3_response(content)

        assert result["impact_score"] == 0.0
        assert result["confidence"] == 0.5  # Default uncertainty
        assert result["rule_violated"] is False

    def test_clamp_score_valid(self, evaluator):
        """Valid scores are returned as-is."""
        assert evaluator._clamp_score(0.5) == 0.5
        assert evaluator._clamp_score(0.0) == 0.0
        assert evaluator._clamp_score(1.0) == 1.0

    def test_clamp_score_out_of_range(self, evaluator):
        """Out-of-range scores are clamped."""
        assert evaluator._clamp_score(-0.5) == 0.0
        assert evaluator._clamp_score(1.5) == 1.0
        assert evaluator._clamp_score(100) == 1.0

    def test_clamp_score_invalid_type(self, evaluator):
        """Invalid types return 0.0."""
        assert evaluator._clamp_score("not a number") == 0.0
        assert evaluator._clamp_score(None) == 0.0
        assert evaluator._clamp_score([1, 2, 3]) == 0.0

    def test_extract_json_from_mixed_content(self, evaluator):
        """JSON is extracted from content with surrounding text."""
        content = """Let me analyze this clause.

The result is: {"impact_score": 0.45, "confidence": 0.88}

That's my assessment."""

        json_str = evaluator._extract_json(content)
        result = json.loads(json_str)

        assert result["impact_score"] == 0.45

    def test_recover_partial_extracts_quote(self, evaluator):
        """Partial recovery extracts quote from malformed JSON."""
        content = '{"impact_score": 0.7, "evidence": {"quote": "ambiguous term", broken'

        result = evaluator._recover_partial_response(content)

        assert result["impact_score"] == 0.7
        assert result["evidence"]["quote"] == "ambiguous term"


# =============================================================================
# TEST: CONTINUOUS SCORING
# =============================================================================


class TestContinuousScoring:
    """Tests for continuous impact_score scoring."""

    @pytest.mark.asyncio
    async def test_evaluate_v3_returns_finding_signal(self, evaluator, mock_wrapper, sample_clause):
        """evaluate_v3_async returns FindingSignal with continuous scoring."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({
                "impact_score": 0.75,
                "confidence": 0.90,
                "rule_violated": True,
                "evidence": {"quote": "as necessary", "explanation": "Ambiguous"},
                "recommendation": "Clarify scope"
            })
        ))

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is not None
        assert isinstance(signal, FindingSignal)
        assert signal.impact_score == 0.75
        assert signal.confidence == 0.90
        assert signal.source == "llm"
        assert signal.severity == "high"  # 0.75 → high

    @pytest.mark.asyncio
    async def test_evaluate_v3_no_violation_returns_none(self, evaluator, mock_wrapper, sample_clause):
        """evaluate_v3_async returns None when no violation."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({
                "impact_score": 0.0,
                "confidence": 0.95,
                "rule_violated": False,
                "evidence": {"quote": "", "explanation": "No issues found"},
                "recommendation": ""
            })
        ))

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is None

    @pytest.mark.asyncio
    async def test_evaluate_v3_low_impact_returns_none(self, evaluator, mock_wrapper, sample_clause):
        """Very low impact_score (<0.05) is treated as no violation."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({
                "impact_score": 0.03,
                "confidence": 0.80,
                "rule_violated": True,  # Even with this true
                "evidence": {"quote": "minor", "explanation": "Very minor issue"},
            })
        ))

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is None  # Below threshold

    @pytest.mark.asyncio
    async def test_evaluate_v3_severity_mapping(self, evaluator, mock_wrapper, sample_clause):
        """impact_score is correctly mapped to severity."""
        test_cases = [
            (0.95, "critical"),
            (0.75, "high"),
            (0.50, "medium"),
            (0.20, "low"),
        ]

        for impact, expected_severity in test_cases:
            mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
                json.dumps({
                    "impact_score": impact,
                    "confidence": 0.90,
                    "evidence": {"quote": "test", "explanation": "test"},
                })
            ))

            signal = await evaluator.evaluate_v3_async(sample_clause)

            assert signal.severity == expected_severity, f"Impact {impact} should map to {expected_severity}"


# =============================================================================
# TEST: COST TRACKING
# =============================================================================


class TestCostTracking:
    """Tests for cost tracking functionality."""

    @pytest.mark.asyncio
    async def test_cost_tracked_per_evaluation(self, evaluator, mock_wrapper, sample_clause):
        """Cost is tracked for each evaluation."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({"impact_score": 0.5, "confidence": 0.8}),
            cost=0.002,
            cached=False,
        ))

        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.total_cost_usd == 0.002
        assert evaluator.llm_calls_count == 1

    @pytest.mark.asyncio
    async def test_cached_evaluation_no_cost(self, evaluator, mock_wrapper, sample_clause):
        """Cached evaluations don't add to cost."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({"impact_score": 0.5, "confidence": 0.8}),
            cost=0.002,
            cached=True,
        ))

        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.total_cost_usd == 0.0  # Not added when cached
        assert evaluator.llm_calls_count == 0
        assert evaluator.metrics.cache_hits == 1

    @pytest.mark.asyncio
    async def test_multiple_evaluations_accumulate(self, evaluator, mock_wrapper, sample_clause):
        """Multiple evaluations accumulate cost."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({"impact_score": 0.5, "confidence": 0.8}),
            cost=0.001,
            cached=False,
        ))

        await evaluator.evaluate_v3_async(sample_clause)
        await evaluator.evaluate_v3_async(sample_clause)
        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.total_cost_usd == 0.003
        assert evaluator.llm_calls_count == 3

    def test_get_statistics_includes_cost(self, evaluator):
        """get_statistics includes cost metrics."""
        evaluator.metrics.record_evaluation(0.005, False, 0.7, 0.9)

        stats = evaluator.get_statistics()

        assert "total_cost_usd" in stats
        assert stats["total_cost_usd"] == 0.005
        assert "llm_calls_count" in stats

    def test_reset_metrics(self, evaluator):
        """reset_metrics clears all counters."""
        evaluator.metrics.record_evaluation(0.005, False, 0.7, 0.9)
        evaluator.evaluations_count = 5
        evaluator.violations_found = 3

        evaluator.reset_metrics()

        assert evaluator.total_cost_usd == 0.0
        assert evaluator.llm_calls_count == 0
        assert evaluator.evaluations_count == 0


# =============================================================================
# TEST: ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self, evaluator, mock_wrapper, sample_clause):
        """API errors result in None (graceful fallback)."""
        mock_wrapper.generate = AsyncMock(side_effect=Exception("API Error"))

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is None

    @pytest.mark.asyncio
    async def test_parse_error_records_metric(self, evaluator, mock_wrapper, sample_clause):
        """Parse errors are recorded in metrics."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            "This is not valid JSON at all",
            cost=0.001,
        ))

        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.metrics.parse_errors == 1

    @pytest.mark.asyncio
    async def test_malformed_response_still_tracks_cost(self, evaluator, mock_wrapper, sample_clause):
        """Even malformed responses track their cost."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            "invalid json",
            cost=0.001,
            cached=False,
        ))

        await evaluator.evaluate_v3_async(sample_clause)

        # Cost still tracked even though response was invalid
        assert evaluator.metrics.evaluations_count == 1


# =============================================================================
# TEST: CATEGORY MAPPING
# =============================================================================


class TestCategoryMapping:
    """Tests for legacy to v0.3 category mapping."""

    def test_category_map_legal(self, mock_wrapper):
        """Legal category maps correctly."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="legal",
        )
        assert evaluator.coherence_category == "LEGAL"

    def test_category_map_financial(self, mock_wrapper):
        """Financial category maps to BUDGET."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="financial",
        )
        assert evaluator.coherence_category == "BUDGET"

    def test_category_map_schedule(self, mock_wrapper):
        """Schedule category maps to TIME."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="schedule",
        )
        assert evaluator.coherence_category == "TIME"

    def test_category_map_unknown_defaults_to_scope(self, mock_wrapper):
        """Unknown categories default to SCOPE."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="unknown_category",
        )
        assert evaluator.coherence_category == "SCOPE"


# =============================================================================
# TEST: PROMPT INTEGRATION
# =============================================================================


class TestPromptIntegration:
    """Tests for prompt template integration."""

    @pytest.mark.asyncio
    async def test_uses_coherence_system_prompt(self, evaluator, mock_wrapper, sample_clause):
        """Evaluation uses COHERENCE_SYSTEM_PROMPT."""
        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({"impact_score": 0.5, "confidence": 0.8})
        ))

        await evaluator.evaluate_v3_async(sample_clause)

        # Check that generate was called with system_prompt
        call_args = mock_wrapper.generate.call_args
        request = call_args[0][0]

        assert "CONTINUOUS IMPACT SCORES" in request.system_prompt
        assert "0.0 to 1.0" in request.system_prompt

    @pytest.mark.asyncio
    async def test_prompt_includes_clause_data(self, evaluator, mock_wrapper):
        """Prompt includes structured clause data when available."""
        clause = Clause(
            id="C1",
            text="Test text",
            data={"budget": 100000, "status": "active"},
        )

        mock_wrapper.generate = AsyncMock(return_value=make_llm_response(
            json.dumps({"impact_score": 0.0, "confidence": 0.9})
        ))

        await evaluator.evaluate_v3_async(clause)

        call_args = mock_wrapper.generate.call_args
        request = call_args[0][0]

        assert "STRUCTURED DATA" in request.prompt
        assert "budget" in request.prompt


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
