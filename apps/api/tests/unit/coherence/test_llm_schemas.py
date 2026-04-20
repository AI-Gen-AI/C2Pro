"""
Tests for coherence/llm_schemas.py.

Verifies that every LLM response schema correctly validates realistic payloads,
applies field clamping, and rejects clearly invalid data.
"""

import pytest

from src.coherence.llm_schemas import (
    ClauseAnalysisLLMResponse,
    CoherenceIssue,
    CoherenceRuleCheckLLMResponse,
    CrossClauseIssue,
    EvidencePayload,
    LlmEvaluationLegacyResponse,
    LlmEvaluationV3Response,
    MultiClauseCoherenceLLMResponse,
)
from src.core.ai.structured_output import parse_llm_json


# ---------------------------------------------------------------------------
# ClauseAnalysisLLMResponse
# ---------------------------------------------------------------------------


class TestClauseAnalysisLLMResponse:
    def test_valid_with_issues(self):
        data = {
            "has_issues": True,
            "issues": [
                {
                    "type": "ambiguity",
                    "severity": "high",
                    "description": "Vague scope",
                    "quote": "as needed",
                    "recommendation": "Specify exact quantities",
                }
            ],
            "confidence": 0.9,
            "reasoning": "Found ambiguous language",
        }
        r = ClauseAnalysisLLMResponse.model_validate(data)
        assert r.has_issues is True
        assert len(r.issues) == 1
        assert r.issues[0].type == "ambiguity"
        assert r.confidence == pytest.approx(0.9)

    def test_no_issues_defaults(self):
        r = ClauseAnalysisLLMResponse.model_validate({"has_issues": False})
        assert r.issues == []
        assert r.confidence == pytest.approx(0.8)
        assert r.reasoning == ""

    def test_confidence_clamped_above_one(self):
        r = ClauseAnalysisLLMResponse.model_validate(
            {"has_issues": False, "confidence": 1.5}
        )
        assert r.confidence == pytest.approx(1.0)

    def test_confidence_clamped_below_zero(self):
        r = ClauseAnalysisLLMResponse.model_validate(
            {"has_issues": False, "confidence": -0.3}
        )
        assert r.confidence == pytest.approx(0.0)

    def test_invalid_issue_type_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClauseAnalysisLLMResponse.model_validate({
                "has_issues": True,
                "issues": [{"type": "unknown_type", "severity": "low", "description": "x"}],
            })

    def test_parse_from_json_string(self):
        json_str = '{"has_issues": false, "issues": [], "confidence": 0.7, "reasoning": "ok"}'
        r = parse_llm_json(json_str, ClauseAnalysisLLMResponse)
        assert r.has_issues is False


# ---------------------------------------------------------------------------
# CoherenceRuleCheckLLMResponse
# ---------------------------------------------------------------------------


class TestCoherenceRuleCheckLLMResponse:
    def test_violated_with_evidence(self):
        data = {
            "rule_violated": True,
            "severity": "critical",
            "evidence": {"quote": "shall be done", "explanation": "passive voice"},
            "confidence": 0.85,
        }
        r = CoherenceRuleCheckLLMResponse.model_validate(data)
        assert r.rule_violated is True
        assert r.severity == "critical"
        assert r.evidence.quote == "shall be done"

    def test_not_violated_defaults(self):
        r = CoherenceRuleCheckLLMResponse.model_validate({"rule_violated": False})
        assert r.severity == "medium"
        assert r.evidence.explanation == ""

    def test_invalid_severity_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CoherenceRuleCheckLLMResponse.model_validate(
                {"rule_violated": False, "severity": "ultra"}
            )


# ---------------------------------------------------------------------------
# MultiClauseCoherenceLLMResponse
# ---------------------------------------------------------------------------


class TestMultiClauseCoherenceLLMResponse:
    def test_with_issues(self):
        data = {
            "cross_clause_issues": [
                {
                    "type": "contradiction",
                    "severity": "high",
                    "affected_clauses": ["C1", "C3"],
                    "description": "Date conflict",
                    "evidence": "C1 says Jan, C3 says Mar",
                }
            ],
            "overall_coherence_score": 60,
            "summary": "Found contradictions",
        }
        r = MultiClauseCoherenceLLMResponse.model_validate(data)
        assert len(r.cross_clause_issues) == 1
        assert r.cross_clause_issues[0].type == "contradiction"
        assert r.overall_coherence_score == 60

    def test_empty_defaults(self):
        r = MultiClauseCoherenceLLMResponse.model_validate({})
        assert r.cross_clause_issues == []
        assert r.overall_coherence_score == 100
        assert r.summary == ""

    def test_score_ge_0_le_100(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MultiClauseCoherenceLLMResponse.model_validate(
                {"overall_coherence_score": 150}
            )


# ---------------------------------------------------------------------------
# LlmEvaluationLegacyResponse
# ---------------------------------------------------------------------------


class TestLlmEvaluationLegacyResponse:
    def test_violated(self):
        data = {
            "rule_violated": True,
            "severity": "high",
            "evidence": {"quote": "works TBD", "explanation": "undefined scope"},
            "confidence": 0.75,
            "recommendation": "Specify scope",
        }
        r = LlmEvaluationLegacyResponse.model_validate(data)
        assert r.rule_violated is True
        assert r.evidence.quote == "works TBD"
        assert r.confidence == pytest.approx(0.75)

    def test_safe_defaults(self):
        r = LlmEvaluationLegacyResponse()
        assert r.rule_violated is False
        assert r.severity == "medium"
        assert r.recommendation == ""

    def test_confidence_clamped(self):
        r = LlmEvaluationLegacyResponse.model_validate(
            {"rule_violated": False, "confidence": 99}
        )
        assert r.confidence == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# LlmEvaluationV3Response
# ---------------------------------------------------------------------------


class TestLlmEvaluationV3Response:
    def test_impact_score_derives_rule_violated(self):
        r = LlmEvaluationV3Response.model_validate({"impact_score": 0.7})
        assert r.rule_violated is True

    def test_low_impact_score_no_violation(self):
        r = LlmEvaluationV3Response.model_validate({"impact_score": 0.02})
        assert r.rule_violated is False

    def test_explicit_rule_violated_respected(self):
        r = LlmEvaluationV3Response.model_validate(
            {"impact_score": 0.9, "rule_violated": False}
        )
        assert r.rule_violated is False

    def test_scores_clamped(self):
        r = LlmEvaluationV3Response.model_validate(
            {"impact_score": 5.0, "confidence": -1.0}
        )
        assert r.impact_score == pytest.approx(1.0)
        assert r.confidence == pytest.approx(0.0)

    def test_evidence_populated(self):
        data = {
            "impact_score": 0.6,
            "evidence": {"quote": "TBD", "explanation": "missing detail"},
            "recommendation": "Add detail",
        }
        r = LlmEvaluationV3Response.model_validate(data)
        assert r.evidence.quote == "TBD"
        assert r.recommendation == "Add detail"

    def test_zero_defaults(self):
        r = LlmEvaluationV3Response()
        assert r.impact_score == pytest.approx(0.0)
        assert r.rule_violated is False
