import os
import sys

# Temporarily add the project root to sys.path to allow imports when run directly
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, "../../../../../"))
sys.path.insert(0, project_root)

from .models import Alert, Clause, CoherenceResult, Evidence, ProjectContext
from .rules import Rule, load_rules
from .rules_engine.base import Finding
from .rules_engine.registry import get_evaluator
from .scoring import ScoringService


class CoherenceEngine:
    """
    Orchestrates the coherence evaluation process.
    It uses a rule registry to delegate the evaluation logic for each rule.
    """

    def __init__(self, rules: list[Rule]):
        self.rules = rules
        self.scoring_service = ScoringService()
        self.evaluators = {
            rule.id: get_evaluator(rule.id) for rule in self.rules if get_evaluator(rule.id)
        }

    def _generate_claim(self, rule: Rule, finding: Finding) -> str:
        """Generates a descriptive claim based on the finding."""
        if rule.id == "project-schedule-delayed":
            return f"Project schedule is marked as '{finding.raw_data.get('status')}'."
        elif rule.id == "project-budget-overrun-10":
            current = finding.raw_data.get("current", "N/A")
            planned = finding.raw_data.get("planned", "N/A")
            percent = finding.raw_data.get("overrun_percentage", 0)
            return f"Budget overrun detected: current spend is {current} against a planned {planned} ({percent:.1f}% over)."
        else:
            return rule.description

    def evaluate(self, project: ProjectContext) -> CoherenceResult:
        """
        Evaluates a project's clauses against all registered rules.
        """
        alerts: list[Alert] = []

        # For each rule, get its evaluator
        for rule in self.rules:
            evaluator_class = self.evaluators.get(rule.id)
            if not evaluator_class:
                continue  # Skip rules with no registered evaluator

            evaluator = evaluator_class()

            # Run the evaluator against every clause in the project
            for clause in project.clauses:
                finding = evaluator.evaluate(clause)

                if finding:
                    # A finding was returned, so create an Alert
                    claim = self._generate_claim(rule, finding)

                    alerts.append(
                        Alert(
                            rule_id=rule.id,
                            severity=rule.severity,
                            category=rule.category or "general",
                            message=f"Alert for rule '{rule.id}' triggered by clause '{finding.triggered_clause.id}'.",
                            evidence=Evidence(
                                source_clause_id=finding.triggered_clause.id,
                                claim=claim,
                                quote=finding.triggered_clause.text,
                            ),
                        )
                    )

        score = self.scoring_service.compute_score(alerts)

        # Compute category breakdown
        category_breakdown = self.scoring_service.compute_category_breakdown(alerts)

        return CoherenceResult(
            overall_score=score,
            alerts=alerts,
            category_breakdown=category_breakdown
        )


if __name__ == "__main__":
    # Note: This block is for direct script execution testing.
    # It might need adjustments if the module structure changes significantly.
    rules_file_path = os.path.join(os.path.dirname(__file__), "initial_rules.yaml")

    if not os.path.exists(rules_file_path):
        print(f"Error: rules file not found at {rules_file_path}")
    else:
        try:
            loaded_rules = load_rules(rules_file_path)
            engine = CoherenceEngine(rules=loaded_rules)

            # --- Test projects using the Clause-based structure ---

            # Clean project
            test_project_clean = ProjectContext(
                id="project-clean-001",
                clauses=[
                    Clause(
                        id="clause-b-001", text="...", data={"planned": 100000, "current": 95000}
                    ),
                    Clause(id="clause-s-001", text="...", data={"status": "on-track"}),
                ],
            )

            # Project with a delayed schedule
            test_project_delayed = ProjectContext(
                id="project-delayed-002",
                clauses=[
                    Clause(
                        id="clause-s-002",
                        text="Schedule is delayed due to supply chain issues.",
                        data={"status": "delayed"},
                    ),
                ],
            )

            # Project with budget overrun
            test_project_overrun = ProjectContext(
                id="project-overrun-003",
                clauses=[
                    Clause(
                        id="clause-b-003",
                        text="Current spend is 250,000 against a 200,000 budget.",
                        data={"planned": 200000, "current": 250000},
                    ),
                ],
            )

            print("\n--- Evaluating project-clean-001 ---")
            result_clean = engine.evaluate(test_project_clean)
            print(f"Score: {result_clean.score}")
            print(f"Alerts: {len(result_clean.alerts)}")

            print("\n--- Evaluating project-delayed-002 ---")
            result_delayed = engine.evaluate(test_project_delayed)
            print(f"Score: {result_delayed.score}")
            if result_delayed.alerts:
                for alert in result_delayed.alerts:
                    print(f"Alert: {alert.evidence.claim}")

            print("\n--- Evaluating project-overrun-003 ---")
            result_overrun = engine.evaluate(test_project_overrun)
            print(f"Score: {result_overrun.score}")
            if result_overrun.alerts:
                for alert in result_overrun.alerts:
                    print(f"Alert: {alert.evidence.claim}")

        except Exception as e:
            print(f"Error during engine initialization or evaluation: {e}")
