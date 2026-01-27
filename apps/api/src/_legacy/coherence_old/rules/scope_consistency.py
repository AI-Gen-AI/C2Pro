"""
C2Pro Coherence Engine - Rule R20: Scope Consistency Check
"""
import json
from typing import Any, Dict, List

import structlog
from pydantic import BaseModel, Field, ValidationError

from src.analysis.adapters.ai.anthropic_client import AIService
from src.core.exceptions import AIServiceError
from ..llm_rule_evaluator import LlmRuleEvaluator
from ..evaluator import RuleEvaluatorContext
from ..models import RuleResult, RuleSeverity, RuleStatus

logger = structlog.get_logger()


# 1. Define the specific Pydantic model for this rule's AI output
class ScopeConsistencyOutput(BaseModel):
    """
    Defines the expected JSON structure from the LLM for the Scope Consistency rule.
    """
    compliant: bool = Field(..., description="True if the budget fully covers the contract scope, False otherwise.")
    missing_items: List[str] = Field(default_factory=list, description="A list of specific work items mentioned in the scope but missing from the budget.")
    analysis_summary: str = Field(..., description="A summary of the analysis, explaining the main gaps or confirming consistency.")


# 2. Implement the rule by inheriting from LlmRuleEvaluator
class RuleScopeConsistency(LlmRuleEvaluator):
    """
    This rule performs a semantic comparison between the contract's scope of work
    and the budget's line items to find discrepancies.

    -   **Rule ID**: R20-SCOPE-CONSISTENCY
    -   **Objective**: Ensure all major work items defined in the contract are
        accounted for in the project budget.
    """

    @property
    def rule_id(self) -> str:
        return "R20-SCOPE-CONSISTENCY"

    @property
    def system_prompt_template(self) -> str:
        return """
You are an expert AI Auditor specializing in construction project management, with the precision of a Quantity Surveyor. Your primary task is to perform a gap analysis between the scope of work defined in a contract and the summary of a project budget.

You will be given two pieces of text:
1.  **Contract Scope**: A description of the work to be performed.
2.  **Budget Summary**: A list of main chapters or line items from the budget.

Your analysis must be methodical and evidence-based. Identify any significant work items that are explicitly or implicitly required by the contract scope but are missing from the budget.

You MUST respond in a valid JSON format, adhering to the following schema:
{
  "compliant": boolean, // true if no gaps are found, false otherwise
  "missing_items": ["item 1", "item 2", ...], // list of missing items
  "analysis_summary": "Your detailed analysis here."
}
"""

    @property
    def user_prompt_template(self) -> str:
        return """
Please perform a scope-to-budget consistency check.

**Constraints:**
- Focus on principal work units and deliverables (e.g., "Structural Steel", "HVAC System", "Perimeter Fencing").
- Ignore minor, generic, or consumable items (e.g., "screws", "safety equipment", "transport").
- If the budget item is generic (e.g., "General Works"), assume it does not cover a specific, major missing item unless explicitly stated.

Here is the data:

---
**CONTRACT SCOPE TEXT**
{contract_scope}
---
**BUDGET SUMMARY**
{budget_summary}
---

Now, provide your analysis in the required JSON format.
"""

    def _prepare_inputs(self, context: RuleEvaluatorContext) -> Dict[str, Any]:
        """
        Extracts the contract scope and budget summary from the context.
        This method assumes the necessary data has been pre-loaded into the context.
        """
        try:
            contract_scope = context.data["contract_scope"]
            budget_summary = context.data["budget_summary"]
            
            # Basic validation and token/length limiting
            # A real implementation would use a proper tokenizer
            if not isinstance(contract_scope, str) or not isinstance(budget_summary, str):
                raise ValueError("Context data for scope and budget must be strings.")

            return {
                "contract_scope": contract_scope[:8000],  # Limit context size
                "budget_summary": budget_summary[:8000],
            }
        except KeyError as e:
            raise ValueError(f"Missing required data in context for Rule R20: {e}")

from sqlalchemy.ext.asyncio import AsyncSession

# ... (imports) ...

# 2. Implement the rule by inheriting from LlmRuleEvaluator
class RuleScopeConsistency(LlmRuleEvaluator):
    # ... (class body) ...
    
    async def evaluate(self, context: RuleEvaluatorContext, db: AsyncSession) -> RuleResult:
        """
        Overrides the base 'evaluate' method to handle the custom logic and
        Pydantic model for this specific rule.
        """
        try:
            prompt_inputs = self._prepare_inputs(context)
            user_prompt = self.user_prompt_template.format(**prompt_inputs)
            
            ai_service = AIService(tenant_id=context.tenant_id, db=db)
            
            raw_response = await ai_service.run_extraction(
                system_prompt=self.system_prompt_template,
                user_content=user_prompt
            )

            llm_output = ScopeConsistencyOutput.model_validate(raw_response)

            # Custom mapping logic for this rule's output
            if llm_output.compliant and not llm_output.missing_items:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=RuleStatus.PASS,
                    message="Scope and budget are consistent.",
                    details={"analysis": llm_output.analysis_summary},
                )
            else:
                # If the AI says it's compliant but still lists items, it's a fail.
                # The presence of missing items is the source of truth.
                rule_result = RuleResult(
                    rule_id=self.rule_id,
                    status=RuleStatus.FAIL,
                    severity=RuleSeverity.HIGH, # This rule is always high-severity if it fails
                    message=f"Scope-budget gap detected. Found {len(llm_output.missing_items)} missing item(s).",
                    details={
                        "missing_items": llm_output.missing_items,
                        "analysis_summary": llm_output.analysis_summary,
                    },
                )

                # Now, try to locate the source of the evidence
                # For this rule, the "evidence" is the summary, not a specific quote.
                # A more advanced implementation might try to locate each missing item.
                # For now, we will skip source location for this specific rule,
                # as the output is an_analysis, not a direct quote.
                
                return rule_result

        except (AIServiceError, ValidationError, ValueError, KeyError) as e:
            # ... (error handling) ...
