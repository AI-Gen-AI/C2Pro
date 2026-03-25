"""State evaluator for validating workflow state mutations.

Validates that state values match expected values using
various comparison operators.
"""

from typing import Any

from golden.evaluators.base import EvaluationResult
from golden.schemas import StateAssertion


class StateEvaluator:
    """Evaluator for workflow state validation.

    Checks that state values at specified JSON paths match
    expected values using operators like equals, contains,
    greater_than, less_than, and exists.
    """

    def evaluate(
        self,
        assertions: list[StateAssertion],
        actual_state: dict[str, Any],
        node_states: dict[str, dict[str, Any]] | None = None,
    ) -> EvaluationResult:
        """Evaluate actual state against expected assertions.

        Args:
            assertions: List of state assertions from the golden case
            actual_state: The final state after workflow execution
            node_states: Optional dict mapping node names to state snapshots
                        at that point (for at_node assertions)

        Returns:
            EvaluationResult with pass/fail status and details
        """
        failures: list[str] = []
        assertion_results: list[dict[str, Any]] = []

        for assertion in assertions:
            # Determine which state to check
            if assertion.at_node and node_states:
                state_to_check = node_states.get(assertion.at_node, {})
                if not state_to_check:
                    failures.append(
                        f"No state snapshot found for node '{assertion.at_node}'"
                    )
                    assertion_results.append({
                        "path": assertion.path,
                        "at_node": assertion.at_node,
                        "passed": False,
                        "reason": "Node state not found",
                    })
                    continue
            else:
                state_to_check = actual_state

            result = self._evaluate_single_assertion(assertion, state_to_check)
            assertion_results.append(result)
            if not result["passed"]:
                failures.append(result["reason"])

        # Calculate score
        if not assertions:
            score = 1.0
        else:
            passed_count = sum(1 for r in assertion_results if r["passed"])
            score = passed_count / len(assertions)

        details = {
            "total_assertions": len(assertions),
            "passed_assertions": sum(1 for r in assertion_results if r["passed"]),
            "assertion_results": assertion_results,
        }

        return EvaluationResult(
            passed=len(failures) == 0,
            score=score,
            failures=failures,
            details=details,
        )

    def _evaluate_single_assertion(
        self,
        assertion: StateAssertion,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate a single state assertion.

        Args:
            assertion: The state assertion to check
            state: The state dictionary to check against

        Returns:
            Dictionary with assertion evaluation details
        """
        actual_value = self._get_value_at_path(state, assertion.path)

        # Handle 'exists' operator specially
        if assertion.operator == "exists":
            exists = actual_value is not None
            expected_exists = bool(assertion.expected_value)
            passed = exists == expected_exists
            return {
                "path": assertion.path,
                "operator": assertion.operator,
                "expected": expected_exists,
                "actual_exists": exists,
                "passed": passed,
                "reason": "" if passed else (
                    f"Path '{assertion.path}' "
                    f"{'exists but should not' if exists else 'does not exist but should'}"
                ),
            }

        # For other operators, value must exist
        if actual_value is None:
            return {
                "path": assertion.path,
                "operator": assertion.operator,
                "expected": assertion.expected_value,
                "actual": None,
                "passed": False,
                "reason": f"Path '{assertion.path}' does not exist in state",
            }

        # Evaluate based on operator
        passed, reason = self._compare_values(
            assertion.operator,
            actual_value,
            assertion.expected_value,
            assertion.path,
        )

        return {
            "path": assertion.path,
            "operator": assertion.operator,
            "expected": assertion.expected_value,
            "actual": actual_value,
            "passed": passed,
            "reason": reason,
        }

    def _get_value_at_path(
        self, state: dict[str, Any], path: str
    ) -> Any | None:
        """Get a value from nested state using dot notation path.

        Supports array indexing with numeric keys (e.g., 'items.0.name').

        Args:
            state: The state dictionary
            path: Dot-separated path (e.g., 'coherence_issues.0.severity')

        Returns:
            The value at the path, or None if path doesn't exist
        """
        current = state
        for key in path.split("."):
            if current is None:
                return None

            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, (list, tuple)):
                try:
                    index = int(key)
                    current = current[index] if 0 <= index < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return current

    def _compare_values(
        self,
        operator: str,
        actual: Any,
        expected: Any,
        path: str,
    ) -> tuple[bool, str]:
        """Compare actual and expected values using the specified operator.

        Args:
            operator: The comparison operator
            actual: The actual value from state
            expected: The expected value from assertion
            path: The state path (for error messages)

        Returns:
            Tuple of (passed, reason_if_failed)
        """
        if operator == "equals":
            passed = actual == expected
            reason = "" if passed else (
                f"Path '{path}' expected {expected!r}, got {actual!r}"
            )
            return passed, reason

        if operator == "contains":
            if isinstance(actual, str) and isinstance(expected, str):
                passed = expected in actual
            elif isinstance(actual, (list, tuple)):
                passed = expected in actual
            elif isinstance(actual, dict):
                passed = expected in actual
            else:
                passed = False
            reason = "" if passed else (
                f"Path '{path}' value {actual!r} does not contain {expected!r}"
            )
            return passed, reason

        if operator == "greater_than":
            try:
                passed = actual > expected
                reason = "" if passed else (
                    f"Path '{path}' value {actual} is not greater than {expected}"
                )
            except TypeError:
                passed = False
                reason = (
                    f"Path '{path}' cannot compare {type(actual).__name__} "
                    f"with {type(expected).__name__}"
                )
            return passed, reason

        if operator == "less_than":
            try:
                passed = actual < expected
                reason = "" if passed else (
                    f"Path '{path}' value {actual} is not less than {expected}"
                )
            except TypeError:
                passed = False
                reason = (
                    f"Path '{path}' cannot compare {type(actual).__name__} "
                    f"with {type(expected).__name__}"
                )
            return passed, reason

        return False, f"Unknown operator: {operator}"
