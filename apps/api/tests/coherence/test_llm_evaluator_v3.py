"""
test_llm_evaluator_v3.py — Tests for LLM Evaluator v0.3 Updates

Tests for Phase 4 LLM Evaluator features:
- Continuous scoring with impact_score (0.0-1.0)
- FindingSignal output
- JSON parsing with error handling
- Cost tracking (total_cost_usd, llm_calls_count)
- Graceful fallback on parse errors

Ported to LLMRulePort injection (TASK-COH-V1-03): mock_wrapper replaced by
fake_llm_port so evaluate_v3_async is tested end-to-end through the port
abstraction without touching the real AnthropicWrapper.

Location: apps/api/tests/coherence/test_llm_evaluator_v3.py
"""

import json
from unittest.mock import AsyncMock

import pytest

from src.coherence.domain.ports.llm_rule_port import LLMRulePort, LLMRuleResult
from src.coherence.models import Clause, FindingSignal
from src.coherence.rules_engine.llm_evaluator import (
    LlmEvaluationMetrics,
    LlmRuleEvaluator,
)

# =============================================================================
# HELPERS
# =============================================================================


def make_llm_result(
    impact_score: float = 0.75,
    confidence: float = 0.90,
    severity: str = "high",
    category: str = "SCOPE",
    evidence_summary: str = "Ambiguous term found",
    quote: str | None = "as necessary",
    cost_usd: float = 0.001,
    cached: bool = False,
) -> LLMRuleResult:
    """Build a canonical LLMRuleResult for tests."""
    return LLMRuleResult(
        rule_id="R-TEST-001",
        clause_id="C1",
        impact_score=impact_score,
        confidence=confidence,
        severity=severity,
        category=category,
        evidence_summary=evidence_summary,
        quote=quote,
        raw_data={
            "cost_usd": cost_usd,
            "cached": cached,
        },
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def fake_port() -> AsyncMock:
    """Fake LLMRulePort backed by AsyncMock(spec=LLMRulePort)."""
    port = AsyncMock(spec=LLMRulePort)
    # Default: returns a violation result
    port.evaluate.return_value = make_llm_result()
    return port


@pytest.fixture
def evaluator(fake_port) -> LlmRuleEvaluator:
    """Create a test evaluator with the fake port injected."""
    return LlmRuleEvaluator(
        rule_id="R-TEST-001",
        rule_name="Test Rule",
        rule_description="A test rule for validation",
        detection_logic="Check for test patterns",
        default_severity="medium",
        category="scope",
        llm_port=fake_port,
    )


@pytest.fixture
def sample_clause() -> Clause:
    """Sample clause for testing."""
    return Clause(
        id="C1",
        text="The contractor shall perform work as necessary and appropriate.",
        data={"category": "scope"},
    )


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


@pytest.mark.asyncio
async def test_v3_evaluator_drops_low_impact_and_low_confidence_results(
    sample_clause: Clause,
) -> None:
    """TASK-COH-LLM-APPLIC-009-P3: calibrated thresholds reject weak LLM
    findings without changing the LLM call path or deterministic rules."""
    low_impact_port = AsyncMock(spec=LLMRulePort)
    low_impact_port.evaluate.return_value = make_llm_result(
        impact_score=0.29,
        confidence=0.95,
    )
    low_impact_evaluator = LlmRuleEvaluator(
        rule_id="R-TEST-001",
        rule_name="Test Rule",
        rule_description="A test rule for validation",
        detection_logic="Check for test patterns",
        category="scope",
        llm_port=low_impact_port,
    )

    assert await low_impact_evaluator.evaluate_v3_async(sample_clause) is None

    low_confidence_port = AsyncMock(spec=LLMRulePort)
    low_confidence_port.evaluate.return_value = make_llm_result(
        impact_score=0.85,
        confidence=0.59,
    )
    low_confidence_evaluator = LlmRuleEvaluator(
        rule_id="R-TEST-001",
        rule_name="Test Rule",
        rule_description="A test rule for validation",
        detection_logic="Check for test patterns",
        category="scope",
        llm_port=low_confidence_port,
    )

    assert await low_confidence_evaluator.evaluate_v3_async(sample_clause) is None


@pytest.mark.asyncio
async def test_v3_evaluator_keeps_substantive_result_at_calibrated_thresholds(
    sample_clause: Clause,
) -> None:
    """TASK-COH-LLM-APPLIC-009-P3: substantive findings at or above both
    configured thresholds are still emitted."""
    port = AsyncMock(spec=LLMRulePort)
    port.evaluate.return_value = make_llm_result(
        impact_score=0.30,
        confidence=0.60,
    )
    evaluator = LlmRuleEvaluator(
        rule_id="R-TEST-001",
        rule_name="Test Rule",
        rule_description="A test rule for validation",
        detection_logic="Check for test patterns",
        category="scope",
        llm_port=port,
    )

    signal = await evaluator.evaluate_v3_async(sample_clause)

    assert signal is not None
    assert signal.impact_score == pytest.approx(0.30)
    assert signal.confidence == pytest.approx(0.60)

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
# TEST: JSON PARSING (v3 schema — returns LlmEvaluationV3Response)
# =============================================================================


class TestJsonParsing:
    """Tests for LLM response JSON parsing via _parse_v3_response.

    Note: _parse_v3_response returns an LlmEvaluationV3Response Pydantic
    object, not a raw dict.  Access fields by attribute, not subscript.
    """

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

        assert result.impact_score == 0.75
        assert result.confidence == 0.90
        assert result.evidence.quote == "as necessary"

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

        assert result.impact_score == 0.60
        assert result.confidence == 0.85

    def test_parse_json_in_generic_code_block(self, evaluator):
        """JSON inside generic code block is extracted."""
        content = """```
{"impact_score": 0.50, "confidence": 0.75}
```"""
        result = evaluator._parse_v3_response(content)

        assert result.impact_score == 0.50

    def test_parse_malformed_json_falls_back_to_zero_impact(self, evaluator):
        """Malformed JSON falls back to safe default (impact_score=0.0)."""
        content = """{"impact_score": 0.80, "confidence": 0.70, broken"""

        result = evaluator._parse_v3_response(content)

        # Safe default from LlmEvaluationV3Response on parse failure
        assert result.impact_score == 0.0

    def test_parse_completely_invalid_returns_safe_default(self, evaluator):
        """Completely invalid content returns safe defaults."""
        content = "This is not JSON at all, just plain text."

        result = evaluator._parse_v3_response(content)

        assert result.impact_score == 0.0
        assert result.rule_violated is False

    def test_parse_result_type_is_pydantic(self, evaluator):
        """_parse_v3_response always returns an LlmEvaluationV3Response."""
        from src.coherence.llm_schemas import LlmEvaluationV3Response

        content = json.dumps({"impact_score": 0.4, "confidence": 0.8})
        result = evaluator._parse_v3_response(content)

        assert isinstance(result, LlmEvaluationV3Response)


# =============================================================================
# TEST: CONTINUOUS SCORING (via port injection)
# =============================================================================


class TestContinuousScoring:
    """Tests for continuous impact_score scoring."""

    @pytest.mark.asyncio
    async def test_evaluate_v3_returns_finding_signal(self, evaluator, fake_port, sample_clause):
        """evaluate_v3_async returns FindingSignal with continuous scoring."""
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.75,
            confidence=0.90,
            severity="high",
        )

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is not None
        assert isinstance(signal, FindingSignal)
        assert signal.impact_score == 0.75
        assert signal.confidence == 0.90
        assert signal.source == "llm"
        assert signal.severity == "high"

    @pytest.mark.asyncio
    async def test_evaluate_v3_no_violation_returns_none(self, evaluator, fake_port, sample_clause):
        """evaluate_v3_async returns None when no violation."""
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.0,
            severity="Info",
            evidence_summary="No issues found",
            quote=None,
        )

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is None

    @pytest.mark.asyncio
    async def test_evaluate_v3_low_impact_returns_none(self, evaluator, fake_port, sample_clause):
        """Very low impact_score (<0.05) is treated as no violation."""
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.03,
            severity="Info",
        )

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is None  # Below threshold

    @pytest.mark.asyncio
    async def test_evaluate_v3_severity_mapping(self, evaluator, fake_port, sample_clause):
        """impact_score is correctly mapped to severity by the port result."""
        test_cases = [
            (0.95, "critical"),
            (0.75, "high"),
            (0.50, "medium"),
        ]

        for impact, expected_severity in test_cases:
            from src.coherence.models import impact_to_severity
            severity = impact_to_severity(impact)
            fake_port.evaluate.return_value = make_llm_result(
                impact_score=impact,
                severity=severity,
            )

            signal = await evaluator.evaluate_v3_async(sample_clause)

            assert signal.severity == expected_severity, (
                f"Impact {impact} should map to {expected_severity}"
            )

        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.20,
            severity="low",
        )
        assert await evaluator.evaluate_v3_async(sample_clause) is None

    @pytest.mark.asyncio
    async def test_port_receives_correct_args(self, evaluator, fake_port, sample_clause):
        """Port is called with expected keyword arguments."""
        fake_port.evaluate.return_value = make_llm_result(impact_score=0.6)

        await evaluator.evaluate_v3_async(sample_clause)

        call_kwargs = fake_port.evaluate.call_args.kwargs
        assert call_kwargs["rule_id"] == "R-TEST-001"
        assert call_kwargs["clause_id"] == "C1"
        assert call_kwargs["clause_text"] == sample_clause.text


# =============================================================================
# TEST: COST TRACKING
# =============================================================================


class TestCostTracking:
    """Tests for cost tracking functionality."""

    @pytest.mark.asyncio
    async def test_cost_tracked_per_evaluation(self, evaluator, fake_port, sample_clause):
        """Cost stored in raw_data is picked up by evaluator metrics."""
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.5,
            cost_usd=0.002,
            cached=False,
        )

        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.total_cost_usd == 0.002
        assert evaluator.llm_calls_count == 1

    @pytest.mark.asyncio
    async def test_cached_evaluation_no_cost(self, evaluator, fake_port, sample_clause):
        """Cached evaluations don't add to cost."""
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.5,
            cost_usd=0.002,
            cached=True,
        )

        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.total_cost_usd == 0.0  # Not added when cached
        assert evaluator.llm_calls_count == 0
        assert evaluator.metrics.cache_hits == 1

    @pytest.mark.asyncio
    async def test_multiple_evaluations_accumulate(self, evaluator, fake_port, sample_clause):
        """Multiple evaluations accumulate cost."""
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.5,
            cost_usd=0.001,
            cached=False,
        )

        await evaluator.evaluate_v3_async(sample_clause)
        await evaluator.evaluate_v3_async(sample_clause)
        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.total_cost_usd == pytest.approx(0.003)
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
    async def test_api_error_returns_none(self, evaluator, fake_port, sample_clause):
        """Port errors result in None (graceful fallback)."""
        fake_port.evaluate.side_effect = Exception("API Error")

        signal = await evaluator.evaluate_v3_async(sample_clause)

        assert signal is None

    @pytest.mark.asyncio
    async def test_malformed_response_still_tracks_evaluation(self, evaluator, fake_port, sample_clause):
        """Even low-impact results track their evaluation."""
        # Return a result with 0 impact (no violation path)
        fake_port.evaluate.return_value = make_llm_result(
            impact_score=0.0,
            severity="Info",
        )

        await evaluator.evaluate_v3_async(sample_clause)

        assert evaluator.metrics.evaluations_count == 1


# =============================================================================
# TEST: CATEGORY MAPPING
# =============================================================================


class TestCategoryMapping:
    """Tests for legacy to v0.3 category mapping."""

    def test_category_map_legal(self, fake_port):
        """Legal category maps correctly."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="legal",
            llm_port=fake_port,
        )
        assert evaluator.coherence_category == "LEGAL"

    def test_category_map_financial(self, fake_port):
        """Financial category maps to BUDGET."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="financial",
            llm_port=fake_port,
        )
        assert evaluator.coherence_category == "BUDGET"

    def test_category_map_schedule(self, fake_port):
        """Schedule category maps to TIME."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="schedule",
            llm_port=fake_port,
        )
        assert evaluator.coherence_category == "TIME"

    def test_category_map_unknown_defaults_to_scope(self, fake_port):
        """Unknown categories default to SCOPE."""
        evaluator = LlmRuleEvaluator(
            rule_id="R-001",
            rule_name="Test",
            rule_description="Test",
            detection_logic="Test",
            category="unknown_category",
            llm_port=fake_port,
        )
        assert evaluator.coherence_category == "SCOPE"


# =============================================================================
# TEST: PORT INTEGRATION
# =============================================================================


class TestPortIntegration:
    """Tests that the port abstraction layer is used correctly.

    Replaces the old TestPromptIntegration which inspected AIRequest internals.
    The port abstracts away prompt building — tests verify port arguments instead.
    """

    @pytest.mark.asyncio
    async def test_port_called_with_rule_metadata(self, evaluator, fake_port, sample_clause):
        """Port.evaluate is called with rule_name and rule_description."""
        fake_port.evaluate.return_value = make_llm_result(impact_score=0.5)

        await evaluator.evaluate_v3_async(sample_clause)

        call_kwargs = fake_port.evaluate.call_args.kwargs
        assert call_kwargs["rule_name"] == "Test Rule"
        assert call_kwargs["rule_description"] == "A test rule for validation"
        assert call_kwargs["detection_logic"] == "Check for test patterns"

    @pytest.mark.asyncio
    async def test_port_called_with_clause_data(self, evaluator, fake_port):
        """Port.evaluate receives clause.data when present."""
        clause = Clause(
            id="C1",
            text="Test text",
            data={"budget": 100000, "status": "active"},
        )
        fake_port.evaluate.return_value = make_llm_result(impact_score=0.0)

        await evaluator.evaluate_v3_async(clause)

        call_kwargs = fake_port.evaluate.call_args.kwargs
        assert call_kwargs["clause_data"] == {"budget": 100000, "status": "active"}


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
