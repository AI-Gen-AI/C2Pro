"""
C2Pro Coherence Engine - Rule R21: Scope Ambiguity Detection
"""
from typing import Any, Dict, List

import structlog
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.ai_service import AIService
from src.core.exceptions import AIServiceError
from ..llm_rule_evaluator import LlmRuleEvaluator
from ..evaluator import RuleEvaluatorContext
from ..models import RuleResult, RuleSeverity, RuleStatus

logger = structlog.get_logger()


# 1. Define the specific Pydantic models for this rule's AI output
class Ambiguity(BaseModel):
    """Represents a single piece of ambiguous language found in the text."""
    term: str = Field(..., description="The exact ambiguous phrase or term.")
    category: str = Field(..., description="A category for the ambiguity (e.g., SUBJECTIVE_QUALITY, UNDEFINED_TIMEFRAME).")
    risk_explanation: str = Field(..., description="Explanation of why this term is a risk.")
    suggested_fix: str = Field(..., description="A concrete suggestion for how to rephrase the term.")

class ScopeAmbiguityOutput(BaseModel):
    """
    Defines the expected JSON structure from the LLM for the Scope Ambiguity rule.
    """
    compliant: bool = Field(..., description="True if the text is perfectly clear and unambiguous, False otherwise.")
    ambiguities: List[Ambiguity] = Field(default_factory=list, description="A list of all ambiguous terms found.")
    overall_clarity_score: int = Field(..., ge=0, le=100, description="A score from 0 (very ambiguous) to 100 (perfectly clear).")


# 2. Implement the rule
class RuleScopeAmbiguity(LlmRuleEvaluator):
    """
    This rule uses an LLM to analyze the Scope of Works for vague, subjective,
    or non-quantifiable language that could lead to disputes.

    -   **Rule ID**: R21-SCOPE-AMBIGUITY
    -   **Objective**: To identify and flag ambiguous terms in the scope description,
        improving clarity and reducing the risk of future claims.
    """

    @property
    def rule_id(self) -> str:
        return "R21-SCOPE-AMBIGUITY"

    @property
    def system_prompt_template(self) -> str:
        return """
You are an expert Contract Manager and forensic analyst. Your personality is extremely strict, precise, and intolerant of any ambiguity. Your goal is to find and eliminate subjective or non-quantifiable language in legal and technical documents to prevent future disputes.

You will analyze a "Scope of Works" text and identify all phrases that are not clear, specific, measurable, and objective. For each ambiguity found, you must explain the risk and suggest a more precise alternative.

You MUST respond in a valid JSON format, adhering to the following schema:
{
  "compliant": boolean, // true ONLY if ZERO ambiguities are found
  "ambiguities": [
    {
      "term": "The ambiguous phrase from the text",
      "category": "A category like SUBJECTIVE_QUALITY, UNDEFINED_TIMEFRAME, UNDEFINED_AUTHORITY, or VAGUE_GENERALIZATION",
      "risk_explanation": "Why this phrase is a contractual risk.",
      "suggested_fix": "A concrete example of better wording."
    }
  ],
  "overall_clarity_score": "An integer from 0 to 100 representing the clarity of the text."
}
"""

    @property
    def user_prompt_template(self) -> str:
        return """
Analyze the following "Scope of Works" text for ambiguity. Identify all vague, subjective, or non-quantifiable phrases.

Focus on detecting terms like the following:
- **Subjective Adjectives**: "adequate", "sufficient", "best practice", "first-class", "high quality", "workmanlike manner".
- **Undefined Timeframes**: "as soon as possible", "in a reasonable time", "promptly", "without delay".
- **Undefined Authority**: "to the satisfaction of the Engineer", "as directed by the Client", "subject to approval".
- **Vague Generalizations**: "etc.", "and similar", "including but not limited to".

For each ambiguity, explain the risk and suggest a specific, measurable alternative.

---
**SCOPE OF WORKS TEXT**
{scope_text}
---

Provide your analysis in the required JSON format. If the text is perfectly clear, return `compliant: true` with an empty `ambiguities` list and a clarity score of 100.
"""

    def _prepare_inputs(self, context: RuleEvaluatorContext) -> Dict[str, Any]:
        """Extracts the scope of work text from the context."""
        try:
            scope_text = context.data["scope_text"]
            if not isinstance(scope_text, str):
                raise ValueError("Context data 'scope_text' must be a string.")
            return {"scope_text": scope_text}
        except KeyError:
            raise ValueError("Missing required 'scope_text' in context for Rule R21.")

    async def evaluate(self, context: RuleEvaluatorContext, db: AsyncSession) -> RuleResult:
        """
        Overrides the base 'evaluate' method to handle the custom logic and
        Pydantic model for the ambiguity detection rule.
        """
        try:
            prompt_inputs = self._prepare_inputs(context)
            user_prompt = self.user_prompt_template.format(**prompt_inputs)
            
            ai_service = AIService(tenant_id=context.tenant_id, db=db)
            
            raw_response = await ai_service.run_extraction(
                system_prompt=self.system_prompt_template,
                user_content=user_prompt
            )

            llm_output = ScopeAmbiguityOutput.model_validate(raw_response)

            # Custom mapping logic
            if llm_output.compliant and not llm_output.ambiguities:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=RuleStatus.PASS,
                    message="The scope of work is clear and unambiguous.",
                    details={"clarity_score": llm_output.overall_clarity_score},
                )
            else:
                # Determine severity based on the nature of the ambiguities found.
                # A simple heuristic: check for high-risk categories or terms.
                # For now, we'll treat any ambiguity as a medium-severity fail.
                highest_severity = RuleSeverity.MEDIUM
                num_ambiguities = len(llm_output.ambiguities)

                # A more advanced version could inspect llm_output.ambiguities
                # for specific high-risk categories to raise severity to HIGH/CRITICAL.

                return RuleResult(
                    rule_id=self.rule_id,
                    status=RuleStatus.FAIL,
                    severity=highest_severity,
                    message=f"Found {num_ambiguities} ambiguous term(s) in the scope of work.",
                    details={
                        "ambiguities": [amb.model_dump() for amb in llm_output.ambiguities],
                        "clarity_score": llm_output.overall_clarity_score,
                    },
                )

        except (AIServiceError, ValidationError, ValueError, KeyError) as e:
            logger.error(
                "rule_r21_evaluation_failed",
                rule_id=self.rule_id,
                project_id=context.project_id,
                error=str(e),
                exc_info=True,
            )
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.ERROR,
                message=f"Rule R21 failed due to a data or service error: {e}",
            )
        except Exception as e:
            logger.exception(
                "rule_r21_unexpected_error",
                rule_id=self.rule_id,
                project_id=context.project_id,
            )
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.ERROR,
                message=f"An unexpected error occurred during Rule R21 evaluation: {e}",
            )
