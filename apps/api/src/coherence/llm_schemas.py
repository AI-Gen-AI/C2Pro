"""
C2Pro - Coherence LLM Response Schemas (Gate S2)

Pydantic models for every LLM→structured-data seam in the coherence module.
These schemas are the authoritative spec; prompts in llm_integration.py and
llm_evaluator.py MUST produce JSON that satisfies them.

Hierarchy:
  ClauseAnalysisLLMResponse        ← CoherenceLLMService.analyze_clause
  CoherenceRuleCheckLLMResponse    ← CoherenceLLMService.check_coherence_rule
  MultiClauseCoherenceLLMResponse  ← CoherenceLLMService.analyze_multi_clause_coherence
  LlmEvaluationLegacyResponse      ← LlmRuleEvaluator._parse_evaluation_response (v1)
  LlmEvaluationV3Response          ← LlmRuleEvaluator._parse_v3_response (v3)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

IssueType = Literal[
    "ambiguity", "risk", "contradiction", "vague_term", "unclear_obligation"
]
SeverityLiteral = Literal["low", "medium", "high", "critical"]
CrossIssueType = Literal["contradiction", "inconsistency", "gap", "overlap"]


# ---------------------------------------------------------------------------
# Clause analysis  (CLAUSE_ANALYSIS_SYSTEM_PROMPT)
# ---------------------------------------------------------------------------


class CoherenceIssue(BaseModel):
    """A single problem found in a clause."""

    type: IssueType
    severity: SeverityLiteral
    description: str
    quote: str = Field(default="")
    recommendation: str = Field(default="")


class ClauseAnalysisLLMResponse(BaseModel):
    """
    Expected JSON shape from CLAUSE_ANALYSIS_SYSTEM_PROMPT.

    Prompt template (llm_integration.py):
        {
            "has_issues": true/false,
            "issues": [...],
            "confidence": 0.0-1.0,
            "reasoning": "..."
        }
    """

    has_issues: bool
    issues: list[CoherenceIssue] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reasoning: str = Field(default="")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: object) -> float:
        try:
            return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.8


# ---------------------------------------------------------------------------
# Rule check  (COHERENCE_CHECK_SYSTEM_PROMPT)
# ---------------------------------------------------------------------------


class EvidencePayload(BaseModel):
    """Evidence block returned by rule-check and evaluator responses."""

    quote: str = Field(default="")
    explanation: str = Field(default="")


class CoherenceRuleCheckLLMResponse(BaseModel):
    """
    Expected JSON shape from COHERENCE_CHECK_SYSTEM_PROMPT.

    Prompt template:
        {
            "rule_violated": true/false,
            "severity": "low|medium|high|critical",
            "evidence": {"quote": "...", "explanation": "..."},
            "confidence": 0.0-1.0
        }
    """

    rule_violated: bool
    severity: SeverityLiteral = Field(default="medium")
    evidence: EvidencePayload = Field(default_factory=EvidencePayload)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: object) -> float:
        try:
            return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.8


# ---------------------------------------------------------------------------
# Multi-clause coherence  (MULTI_CLAUSE_COHERENCE_PROMPT)
# ---------------------------------------------------------------------------


class CrossClauseIssue(BaseModel):
    """A single cross-clause coherence problem."""

    type: CrossIssueType
    severity: SeverityLiteral
    affected_clauses: list[str] = Field(default_factory=list)
    description: str
    evidence: str = Field(default="")


class MultiClauseCoherenceLLMResponse(BaseModel):
    """
    Expected JSON shape from MULTI_CLAUSE_COHERENCE_PROMPT.

    Prompt template:
        {
            "cross_clause_issues": [...],
            "overall_coherence_score": 0-100,
            "summary": "..."
        }
    """

    cross_clause_issues: list[CrossClauseIssue] = Field(default_factory=list)
    overall_coherence_score: int = Field(default=100, ge=0, le=100)
    summary: str = Field(default="")


# ---------------------------------------------------------------------------
# LLM evaluator v1  (LlmRuleEvaluator._parse_evaluation_response)
# ---------------------------------------------------------------------------


class LlmEvaluationLegacyResponse(BaseModel):
    """
    Expected JSON shape from the v1 rule evaluator prompt.

    Prompt template (llm_evaluator.py _build_evaluation_prompt):
        {
            "rule_violated": true/false,
            "severity": "low|medium|high|critical",
            "evidence": {"quote": "...", "explanation": "..."},
            "confidence": 0.0-1.0,
            "recommendation": "..."
        }
    """

    rule_violated: bool = Field(default=False)
    severity: SeverityLiteral = Field(default="medium")
    evidence: EvidencePayload = Field(default_factory=EvidencePayload)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    recommendation: str = Field(default="")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: object) -> float:
        try:
            return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.8


# ---------------------------------------------------------------------------
# LLM evaluator v3  (LlmRuleEvaluator._parse_v3_response)
# ---------------------------------------------------------------------------


class LlmEvaluationV3Response(BaseModel):
    """
    Expected JSON shape from the v3 rule evaluator prompt (continuous scoring).

    Prompt template (coherence/graph/prompts.py build_evaluation_prompt):
        {
            "impact_score": 0.0-1.0,
            "confidence": 0.0-1.0,
            "rule_violated": true/false,
            "evidence": {"quote": "...", "explanation": "..."},
            "recommendation": "..."
        }

    rule_violated defaults to (impact_score > 0.05) when not supplied by
    the model, preserving backward compatibility with older prompts.
    """

    impact_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    rule_violated: bool = Field(default=False)
    evidence: EvidencePayload = Field(default_factory=EvidencePayload)
    recommendation: str = Field(default="")

    @field_validator("impact_score", "confidence", mode="before")
    @classmethod
    def _clamp_to_unit(cls, v: object) -> float:
        try:
            return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    @model_validator(mode="after")
    def _derive_rule_violated(self) -> LlmEvaluationV3Response:
        """Derive rule_violated from impact_score when not explicitly set."""
        if "rule_violated" not in self.model_fields_set:
            self.rule_violated = self.impact_score > 0.05
        return self
