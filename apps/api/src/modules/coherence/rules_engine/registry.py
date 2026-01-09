# apps/api/src/modules/coherence/rules_engine/registry.py

from .base import RuleEvaluator
from .deterministic import (
    BudgetOverrunEvaluator,
    ContractReviewOverdueEvaluator,
    ScheduleDelayEvaluator,
)

# The Rule Registry
# This dictionary maps a rule's ID (from the rules.yaml) to the
# concrete RuleEvaluator class that implements its logic.
RULE_EVALUATORS: dict[str, type[RuleEvaluator]] = {
    "project-budget-overrun-10": BudgetOverrunEvaluator,
    "project-schedule-delayed": ScheduleDelayEvaluator,
    "project-contract-review-overdue": ContractReviewOverdueEvaluator,
}


def get_evaluator(rule_id: str) -> type[RuleEvaluator] | None:
    """
    Retrieves the evaluator class for a given rule ID from the registry.

    Args:
        rule_id: The ID of the rule.

    Returns:
        The corresponding RuleEvaluator class, or None if not found.
    """
    return RULE_EVALUATORS.get(rule_id)


def register_evaluator(rule_id: str, evaluator_class: type[RuleEvaluator]):
    """
    Registers a new evaluator class for a given rule ID.
    This allows for dynamic registration of rules.
    """
    if rule_id in RULE_EVALUATORS:
        # In a real application, you might want to log a warning here.
        pass
    RULE_EVALUATORS[rule_id] = evaluator_class
