"""
C2Pro Coherence Engine - LLM-based Rule Evaluator

This file provides the abstract base class for rule evaluators that use
a Large Language Model to perform semantic or qualitative analysis.
"""
import json
from abc import abstractmethod
from typing import Dict, Any

import structlog
from pydantic import BaseModel, Field, ValidationError

from src.ai.ai_service import AIService
from src.core.exceptions import AIServiceError
from .evaluator import RuleEvaluator, RuleEvaluatorContext
from .models import RuleResult, RuleSeverity, RuleStatus

logger = structlog.get_logger()


class LlmEvaluationOutput(BaseModel):
    """
    Pydantic model for the expected JSON output from the LLM.
    This enforces a strict schema on the AI's response.
    """
    compliant: bool = Field(..., description="True if the check passes (no issues found), False otherwise.")
    reasoning: str = Field(..., description="A detailed explanation of why the check passed or failed.")
    severity: RuleSeverity = Field(..., description="The severity of the issue if not compliant.")
    evidence_quote: str | None = Field(None, description="A direct quote from the source text that supports the reasoning.")


class LlmRuleEvaluator(RuleEvaluator):
    """
    An abstract base class for rules that rely on an LLM for evaluation.

    This class handles the "dirty work" of prompt rendering, calling the AI service,
    parsing the response, and handling errors, allowing subclasses to focus purely
    on defining the prompt and preparing the inputs.
    """

    @property
    @abstractmethod
    def system_prompt_template(self) -> str:
        """The base system prompt that defines the LLM's persona and overall goal."""
        raise NotImplementedError

    @property
    @abstractmethod
    def user_prompt_template(self) -> str:
        """
        The user-facing prompt template with placeholders for context variables.
        Example: "Compare Text A: {text_a} with Text B: {text_b}"
        """
        raise NotImplementedError

    @abstractmethod
    def _prepare_inputs(self, context: RuleEvaluatorContext) -> Dict[str, Any]:
        """
        A hook for subclasses to extract and prepare variables for the prompt templates
        from the main evaluation context.

        Args:
            context: The main evaluation context.

        Returns:
            A dictionary of variables to be injected into the prompt templates.
        """
        raise NotImplementedError

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.source_locator import SourceLocator

# ... (imports remain the same) ...

class LlmRuleEvaluator(RuleEvaluator):
    # ... (rest of the class is the same until evaluate) ...

    async def evaluate(self, context: RuleEvaluatorContext, db: AsyncSession) -> RuleResult:
        """
        Orchestrates the evaluation by rendering prompts, calling the LLM,
        parsing the result, and locating the source of evidence.
        """
        try:
            prompt_inputs = self._prepare_inputs(context)
            user_prompt = self.user_prompt_template.format(**prompt_inputs)
            
            # The AIService needs a tenant_id, which is in the context
            ai_service = AIService(tenant_id=context.tenant_id, db=db)
            
            raw_response = await ai_service.run_extraction(
                system_prompt=self.system_prompt_template,
                user_content=user_prompt
            )

            llm_output = LlmEvaluationOutput.model_validate(raw_response)
            rule_result = self._map_llm_output_to_rule_result(llm_output)

            # If the rule failed and there's an evidence quote, try to locate it
            if rule_result.status == RuleStatus.FAIL and llm_output.evidence_quote:
                document_id = context.data.get("document_id")
                if document_id:
                    locator = SourceLocator(db)
                    location = await locator.locate_evidence(llm_output.evidence_quote, document_id)
                    if location:
                        rule_result.details['evidence_location'] = location.model_dump()
                else:
                    logger.warning("llm_rule_evaluator_missing_doc_id", rule_id=self.rule_id)

            return rule_result

        except (AIServiceError, ValidationError, KeyError, json.JSONDecodeError) as e:
            logger.error(
                "llm_rule_evaluation_failed",
                rule_id=self.rule_id,
                project_id=context.project_id,
                error=str(e),
                exc_info=True,
            )
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.ERROR,
                message=f"Rule evaluation failed due to an AI service or data parsing error: {e}",
            )
        except Exception as e:
            logger.exception(
                "llm_rule_evaluation_unexpected_error",
                rule_id=self.rule_id,
                project_id=context.project_id,
            )
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.ERROR,
                message=f"An unexpected error occurred during rule evaluation: {e}",
            )

    # ... (the rest of the file is the same) ...


    def _map_llm_output_to_rule_result(self, llm_output: LlmEvaluationOutput) -> RuleResult:
        """Maps the validated output from the LLM to the standardized RuleResult."""
        if llm_output.compliant:
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.PASS,
                message="The rule check was successful with no discrepancies found.",
                details={"reasoning": llm_output.reasoning},
            )
        else:
            return RuleResult(
                rule_id=self.rule_id,
                status=RuleStatus.FAIL,
                severity=llm_output.severity,
                message=llm_output.reasoning,
                details={
                    "reasoning": llm_output.reasoning,
                    "evidence_quote": llm_output.evidence_quote,
                },
            )
