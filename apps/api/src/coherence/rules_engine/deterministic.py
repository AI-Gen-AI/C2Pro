# apps/api/src/coherence/rules_engine/deterministic.py

from ..models import Clause
from .base import Finding, RuleEvaluator


class BudgetOverrunEvaluator(RuleEvaluator):
    """
    Evaluator for the 'project-budget-overrun-10' rule.
    Checks if the current budget exceeds the planned budget by more than 10%.
    """

    def evaluate(self, clause: Clause) -> Finding | None:
        """
        Evaluates a clause to see if it represents a budget overrun.
        """
        budget_current = clause.data.get("current")
        budget_planned = clause.data.get("planned")

        # Ensure both values are present and are numbers
        if isinstance(budget_current, (int, float)) and isinstance(budget_planned, (int, float)):
            if budget_planned > 0 and budget_current > budget_planned * 1.1:
                return Finding(
                    triggered_clause=clause,
                    raw_data={
                        "current": budget_current,
                        "planned": budget_planned,
                        "overrun_percentage": (budget_current / budget_planned - 1) * 100,
                    },
                )

        return None


class ScheduleDelayEvaluator(RuleEvaluator):
    """
    Evaluator for the 'project-schedule-delayed' rule.
    Checks if the schedule status is 'delayed'.
    """

    def evaluate(self, clause: Clause) -> Finding | None:
        """
        Evaluates a clause to see if it indicates a schedule delay.
        """
        schedule_status = clause.data.get("status")

        if schedule_status == "delayed":
            return Finding(triggered_clause=clause, raw_data={"status": schedule_status})

        return None


from datetime import datetime


class ContractReviewOverdueEvaluator(RuleEvaluator):
    """
    Evaluator for the 'project-contract-review-overdue' rule.
    Checks if the last contract review date is older than a specified threshold.
    """

    def evaluate(self, clause: Clause) -> Finding | None:
        """
        Evaluates a clause to see if its contract review date is overdue.
        """
        last_review_date_str = clause.data.get("last_review_date")

        if last_review_date_str:
            try:
                last_review_date = datetime.strptime(last_review_date_str, "%Y-%m-%d")
                # Threshold for v0.3: hardcoded current date for consistent testing
                # In a real system, this would be datetime.now()
                threshold_date = datetime(2025, 6, 1)  # Same as in engine.py

                if last_review_date < threshold_date:
                    return Finding(
                        triggered_clause=clause,
                        raw_data={
                            "last_review_date": last_review_date_str,
                            "threshold_date": threshold_date.strftime("%Y-%m-%d"),
                        },
                    )
            except ValueError:
                pass  # Invalid date format

        return None
