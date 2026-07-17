"""
Concrete adapter for LLMRulePort - wraps AnthropicWrapper.

Test Suite ID: TS-UD-COH-RUL-001
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from src.coherence.domain.ports.llm_rule_port import LLMRuleResult
from src.coherence.graph.prompts import (
    COHERENCE_SYSTEM_PROMPT,
    build_evaluation_prompt,
)
from src.coherence.llm_schemas import LlmEvaluationV3Response
from src.coherence.models import CoherenceCategory, impact_to_severity
from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType
from src.core.ai.structured_output import LLMSchemaError, parse_llm_json

logger = structlog.get_logger()


@dataclass
class LLMRuleEvaluatorAdapter:
    """
    Concrete implementation of LLMRulePort using AnthropicWrapper.

    This adapter bridges the domain port with the infrastructure
    layer's AnthropicWrapper.

    Example:
        adapter = LLMRuleEvaluatorAdapter()
        result = await adapter.evaluate(
            rule_id="R-SCOPE-01",
            rule_name="Scope Clarity",
            ...
        )
    """

    _wrapper: AnthropicWrapper | None = None

    def __init__(self, wrapper: AnthropicWrapper | None = None):
        """
        Initialize the adapter.

        Args:
            wrapper: Custom AnthropicWrapper. If None, uses singleton.
        """
        self._wrapper = wrapper

    @property
    def wrapper(self) -> AnthropicWrapper:
        """Get the underlying wrapper (lazy singleton)."""
        if self._wrapper is None:
            self._wrapper = get_anthropic_wrapper()
        return self._wrapper

    def _map_category(self, category: str) -> CoherenceCategory:
        """Map legacy category string to CoherenceCategory."""
        mapping: dict[str, CoherenceCategory] = {
            "general": "SCOPE",
            "scope": "SCOPE",
            "financial": "BUDGET",
            "legal": "LEGAL",
            "technical": "TECHNICAL",
            "schedule": "TIME",
            "quality": "QUALITY",
        }
        return mapping.get(category.lower(), "SCOPE")

    async def evaluate(
        self,
        *,
        rule_id: str,
        rule_name: str,
        rule_description: str,
        detection_logic: str,
        category: str,
        clause_id: str,
        clause_text: str,
        clause_data: dict[str, Any] | None = None,
        tenant_id: UUID | None = None,
    ) -> LLMRuleResult:
        """
        Evaluates a clause against a coherence rule using LLM.

        Implements LLMRulePort.evaluate().
        """
        logger.info(
            "llm_rule_evaluating",
            rule_id=rule_id,
            clause_id=clause_id,
        )

        coherence_category = self._map_category(category)

        prompt = build_evaluation_prompt(
            rule_id=rule_id,
            rule_name=rule_name,
            rule_description=rule_description,
            detection_logic=detection_logic,
            category=coherence_category,
            clause_id=clause_id,
            clause_text=clause_text,
            clause_data=clause_data,
        )

        request = AIRequest(
            prompt=prompt,
            task_type=AITaskType.COHERENCE_CHECK,
            system_prompt=COHERENCE_SYSTEM_PROMPT,
            low_budget_mode=False,
            tenant_id=tenant_id,
            use_cache=True,
            temperature=0.0,
        )

        try:
            response = await self.wrapper.generate(request)

            result = self._parse_v3_response(response.content)

            impact_score = result.impact_score
            confidence = result.confidence
            severity = impact_to_severity(impact_score)

            if impact_score < 0.05:
                logger.debug(
                    "llm_rule_no_violation",
                    rule_id=rule_id,
                    clause_id=clause_id,
                    impact_score=impact_score,
                )
                return LLMRuleResult(
                    rule_id=rule_id,
                    clause_id=clause_id,
                    impact_score=0.0,
                    confidence=confidence,
                    severity="Info",
                    category=coherence_category,
                    evidence_summary="No violation detected",
                    quote=None,
                    raw_data={"model_used": response.model_used, "cached": response.cached},
                )

            return LLMRuleResult(
                rule_id=rule_id,
                clause_id=clause_id,
                impact_score=impact_score,
                confidence=confidence,
                severity=severity,
                category=coherence_category,
                evidence_summary=result.evidence.explanation,
                quote=result.evidence.quote,
                raw_data={
                    "recommendation": result.recommendation,
                    "model_used": response.model_used,
                    "cached": response.cached,
                    "cost_usd": response.cost_usd,
                },
            )

        except Exception as e:
            logger.error(
                "llm_evaluation_failed",
                rule_id=rule_id,
                clause_id=clause_id,
                error=str(e),
            )
            return LLMRuleResult(
                rule_id=rule_id,
                clause_id=clause_id,
                impact_score=0.0,
                confidence=0.0,
                severity="Info",
                category=coherence_category,
                evidence_summary=f"Evaluation failed: {str(e)}",
                quote=None,
                raw_data={"error": str(e)},
            )

    def _parse_v3_response(self, content: str) -> LlmEvaluationV3Response:
        """Parse and validate LLM response against schema."""
        try:
            return parse_llm_json(content, LlmEvaluationV3Response)
        except LLMSchemaError as e:
            logger.warning(
                "llm_response_parse_failed",
                error=str(e),
                content_preview=content[:200],
            )
            return LlmEvaluationV3Response()


def get_llm_rule_evaluator() -> LLMRuleEvaluatorAdapter:
    """
    Factory to get the LLMRulePort implementation.

    Returns:
        LLMRuleEvaluatorAdapter instance implementing LLMRulePort.
    """
    return LLMRuleEvaluatorAdapter()
