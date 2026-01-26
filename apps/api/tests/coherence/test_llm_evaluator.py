# tests/coherence/test_llm_evaluator.py
"""
C2Pro - LLM Rule Evaluator Tests (CE-25)

Unit tests for the LlmRuleEvaluator class.
Uses mocking to ensure deterministic test results.

Version: 1.0.0
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.coherence.models import Clause
from src.modules.coherence.rules_engine.base import Finding


# ===========================================
# TEST: LlmRuleEvaluator INITIALIZATION
# ===========================================


class TestLlmRuleEvaluatorInit:
    """Tests for LlmRuleEvaluator initialization."""

    def test_evaluator_initializes_with_required_params(self, patch_anthropic_wrapper):
        """Test that evaluator initializes correctly with required parameters."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-001",
            rule_name="Test Rule",
            rule_description="A test rule",
            detection_logic="Check for ambiguous terms",
        )

        assert evaluator.rule_id == "TEST-001"
        assert evaluator.rule_name == "Test Rule"
        assert evaluator.rule_description == "A test rule"
        assert evaluator.detection_logic == "Check for ambiguous terms"
        assert evaluator.default_severity == "medium"  # Default
        assert evaluator.category == "general"  # Default

    def test_evaluator_initializes_with_all_params(self, patch_anthropic_wrapper):
        """Test that evaluator initializes correctly with all parameters."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator
        from uuid import uuid4

        tenant_id = uuid4()
        evaluator = LlmRuleEvaluator(
            rule_id="TEST-002",
            rule_name="Full Test Rule",
            rule_description="A fully configured test rule",
            detection_logic="Detailed detection logic",
            default_severity="high",
            category="legal",
            low_budget_mode=True,
            tenant_id=tenant_id,
        )

        assert evaluator.rule_id == "TEST-002"
        assert evaluator.default_severity == "high"
        assert evaluator.category == "legal"
        assert evaluator.low_budget_mode is True
        assert evaluator.tenant_id == tenant_id


# ===========================================
# TEST: LlmRuleEvaluator EVALUATION
# ===========================================


class TestLlmRuleEvaluatorEvaluate:
    """Tests for LlmRuleEvaluator.evaluate_async method."""

    @pytest.mark.asyncio
    async def test_evaluate_returns_finding_on_violation(
        self,
        patch_anthropic_wrapper,
        sample_clause_ambiguous,
    ):
        """Test that evaluate returns Finding when rule is violated."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="R-SCOPE-CLARITY-01",
            rule_name="Scope Clarity",
            rule_description="Check scope clarity",
            detection_logic="Find ambiguous terms",
            default_severity="high",
            category="scope",
        )

        finding = await evaluator.evaluate_async(sample_clause_ambiguous)

        assert finding is not None
        assert isinstance(finding, Finding)
        assert finding.triggered_clause.id == sample_clause_ambiguous.id
        assert finding.raw_data["rule_id"] == "R-SCOPE-CLARITY-01"
        assert finding.raw_data["severity"] == "high"
        assert "evidence" in finding.raw_data

    @pytest.mark.asyncio
    async def test_evaluate_returns_none_on_no_violation(
        self,
        mock_anthropic_wrapper_no_violation,
        sample_clause_clear,
    ):
        """Test that evaluate returns None when no violation is found."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        with patch(
            "src.modules.coherence.rules_engine.llm_evaluator.get_anthropic_wrapper",
            return_value=mock_anthropic_wrapper_no_violation
        ):
            evaluator = LlmRuleEvaluator(
                rule_id="R-SCOPE-CLARITY-01",
                rule_name="Scope Clarity",
                rule_description="Check scope clarity",
                detection_logic="Find ambiguous terms",
            )

            finding = await evaluator.evaluate_async(sample_clause_clear)

            assert finding is None

    @pytest.mark.asyncio
    async def test_evaluate_updates_statistics(
        self,
        patch_anthropic_wrapper,
        sample_clause_ambiguous,
    ):
        """Test that evaluate updates evaluator statistics."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-STATS",
            rule_name="Stats Test",
            rule_description="Test statistics",
            detection_logic="Detect issues",
        )

        assert evaluator.evaluations_count == 0
        assert evaluator.violations_found == 0

        await evaluator.evaluate_async(sample_clause_ambiguous)

        assert evaluator.evaluations_count == 1
        assert evaluator.violations_found == 1
        assert evaluator.total_cost > 0

    @pytest.mark.asyncio
    async def test_evaluate_handles_cached_response(
        self,
        mock_llm_response_violation,
        sample_clause_ambiguous,
    ):
        """Test that cached responses are handled correctly."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator
        from tests.coherence.conftest import MockAIResponse

        mock_wrapper = MagicMock()
        mock_wrapper.generate = AsyncMock(
            return_value=MockAIResponse(mock_llm_response_violation, cached=True)
        )

        with patch(
            "src.modules.coherence.rules_engine.llm_evaluator.get_anthropic_wrapper",
            return_value=mock_wrapper
        ):
            evaluator = LlmRuleEvaluator(
                rule_id="TEST-CACHE",
                rule_name="Cache Test",
                rule_description="Test caching",
                detection_logic="Detect issues",
            )

            finding = await evaluator.evaluate_async(sample_clause_ambiguous)

            assert finding is not None
            assert finding.raw_data["cached"] is True


# ===========================================
# TEST: PROMPT BUILDING
# ===========================================


class TestLlmRuleEvaluatorPromptBuilding:
    """Tests for prompt building methods."""

    def test_build_evaluation_prompt_includes_clause_text(self, patch_anthropic_wrapper):
        """Test that evaluation prompt includes clause text."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-PROMPT",
            rule_name="Prompt Test",
            rule_description="Test prompt building",
            detection_logic="Find issues",
        )

        clause = Clause(id="C1", text="Test clause text here", data={})
        prompt = evaluator._build_evaluation_prompt(clause)

        assert "C1" in prompt
        assert "Test clause text here" in prompt

    def test_build_evaluation_prompt_includes_detection_logic(self, patch_anthropic_wrapper):
        """Test that evaluation prompt includes detection logic."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        detection_logic = "Check for ambiguous terms like 'razonable'"
        evaluator = LlmRuleEvaluator(
            rule_id="TEST-PROMPT",
            rule_name="Prompt Test",
            rule_description="Test prompt building",
            detection_logic=detection_logic,
        )

        clause = Clause(id="C1", text="Test text", data={})
        prompt = evaluator._build_evaluation_prompt(clause)

        assert detection_logic in prompt

    def test_build_evaluation_prompt_includes_clause_data(self, patch_anthropic_wrapper):
        """Test that evaluation prompt includes clause data when present."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-PROMPT",
            rule_name="Prompt Test",
            rule_description="Test prompt building",
            detection_logic="Find issues",
        )

        clause = Clause(
            id="C1",
            text="Test text",
            data={"amount": 10000, "currency": "USD"}
        )
        prompt = evaluator._build_evaluation_prompt(clause)

        assert "10000" in prompt
        assert "USD" in prompt

    def test_build_system_prompt_includes_rule_info(self, patch_anthropic_wrapper):
        """Test that system prompt includes rule information."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-SYSTEM",
            rule_name="System Prompt Test",
            rule_description="Test system prompt building",
            detection_logic="Find issues",
            category="financial",
        )

        system_prompt = evaluator._build_system_prompt()

        assert "System Prompt Test" in system_prompt
        assert "Test system prompt building" in system_prompt
        assert "financial" in system_prompt


# ===========================================
# TEST: RESPONSE PARSING
# ===========================================


class TestLlmRuleEvaluatorResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_valid_json_response(self, patch_anthropic_wrapper):
        """Test parsing of valid JSON response."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-PARSE",
            rule_name="Parse Test",
            rule_description="Test parsing",
            detection_logic="Find issues",
        )

        valid_json = '{"rule_violated": true, "severity": "high"}'
        result = evaluator._parse_evaluation_response(valid_json)

        assert result["rule_violated"] is True
        assert result["severity"] == "high"

    def test_parse_json_with_markdown_code_block(self, patch_anthropic_wrapper):
        """Test parsing JSON wrapped in markdown code block."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-PARSE",
            rule_name="Parse Test",
            rule_description="Test parsing",
            detection_logic="Find issues",
        )

        markdown_json = '```json\n{"rule_violated": true}\n```'
        result = evaluator._parse_evaluation_response(markdown_json)

        assert result["rule_violated"] is True

    def test_parse_invalid_json_returns_safe_default(self, patch_anthropic_wrapper):
        """Test that invalid JSON returns safe default."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-PARSE",
            rule_name="Parse Test",
            rule_description="Test parsing",
            detection_logic="Find issues",
        )

        invalid_json = "This is not valid JSON"
        result = evaluator._parse_evaluation_response(invalid_json)

        assert result["rule_violated"] is False
        assert "parse_error" in result


# ===========================================
# TEST: STATISTICS
# ===========================================


class TestLlmRuleEvaluatorStatistics:
    """Tests for evaluator statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics_returns_correct_data(
        self,
        patch_anthropic_wrapper,
        sample_clause_ambiguous,
    ):
        """Test that get_statistics returns correct data."""
        from src.modules.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator

        evaluator = LlmRuleEvaluator(
            rule_id="TEST-STATS",
            rule_name="Stats Test",
            rule_description="Test statistics",
            detection_logic="Detect issues",
        )

        # Perform some evaluations
        await evaluator.evaluate_async(sample_clause_ambiguous)

        stats = evaluator.get_statistics()

        assert stats["rule_id"] == "TEST-STATS"
        assert stats["rule_name"] == "Stats Test"
        assert stats["evaluations_count"] == 1
        assert stats["violations_found"] == 1
        assert "violation_rate" in stats
        assert "total_cost_usd" in stats


# ===========================================
# TEST: FACTORY FUNCTIONS
# ===========================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_llm_evaluator_from_rule(self, patch_anthropic_wrapper):
        """Test creating evaluator from rule dictionary."""
        from src.modules.coherence.rules_engine.llm_evaluator import (
            create_llm_evaluator_from_rule,
        )

        rule = {
            "id": "R-TEST-001",
            "name": "Test Rule",
            "description": "A test rule description",
            "detection_logic": "Find ambiguous terms",
            "default_severity": "high",
            "category": "scope",
        }

        evaluator = create_llm_evaluator_from_rule(rule, low_budget_mode=True)

        assert evaluator.rule_id == "R-TEST-001"
        assert evaluator.rule_name == "Test Rule"
        assert evaluator.rule_description == "A test rule description"
        assert evaluator.detection_logic == "Find ambiguous terms"
        assert evaluator.default_severity == "high"
        assert evaluator.category == "scope"
        assert evaluator.low_budget_mode is True

    def test_get_predefined_llm_evaluators(self, patch_anthropic_wrapper):
        """Test getting predefined evaluators."""
        from src.modules.coherence.rules_engine.llm_evaluator import (
            get_predefined_llm_evaluators,
            QUALITATIVE_RULES,
        )

        evaluators = get_predefined_llm_evaluators(low_budget_mode=True)

        assert len(evaluators) == len(QUALITATIVE_RULES)
        for evaluator in evaluators:
            assert evaluator.low_budget_mode is True


# ===========================================
# TEST: QUALITATIVE RULES
# ===========================================


class TestQualitativeRules:
    """Tests for predefined qualitative rules."""

    def test_qualitative_rules_have_required_fields(self):
        """Test that all qualitative rules have required fields."""
        from src.modules.coherence.rules_engine.llm_evaluator import QUALITATIVE_RULES

        required_fields = ["id", "name", "description", "detection_logic", "category"]

        for rule in QUALITATIVE_RULES:
            for field in required_fields:
                assert field in rule, f"Rule {rule.get('id')} missing {field}"

    def test_qualitative_rules_have_valid_severities(self):
        """Test that all rules have valid severity levels."""
        from src.modules.coherence.rules_engine.llm_evaluator import QUALITATIVE_RULES

        valid_severities = {"critical", "high", "medium", "low"}

        for rule in QUALITATIVE_RULES:
            severity = rule.get("default_severity", "medium")
            assert severity in valid_severities, f"Invalid severity in rule {rule['id']}"

    def test_qualitative_rules_have_unique_ids(self):
        """Test that all qualitative rules have unique IDs."""
        from src.modules.coherence.rules_engine.llm_evaluator import QUALITATIVE_RULES

        ids = [rule["id"] for rule in QUALITATIVE_RULES]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs found"
