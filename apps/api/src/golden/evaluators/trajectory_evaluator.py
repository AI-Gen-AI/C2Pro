"""Trajectory evaluator for graph traversal paths.

Validates that the actual node traversal sequence matches
the expected trajectory constraints defined in golden cases.
"""

from collections import Counter

from golden.evaluators.base import EvaluationResult
from golden.schemas import TrajectoryConstraint


class TrajectoryEvaluator:
    """Evaluator for LangGraph trajectory (node traversal) validation.

    Checks that:
    - All required nodes were visited
    - No forbidden nodes were visited
    - Loop count is within allowed limits
    """

    def evaluate(
        self, constraint: TrajectoryConstraint, actual_nodes: list[str]
    ) -> EvaluationResult:
        """Evaluate actual trajectory against expected constraints.

        Args:
            constraint: The trajectory constraints from the golden case
            actual_nodes: The actual sequence of nodes visited

        Returns:
            EvaluationResult with pass/fail status and details
        """
        failures: list[str] = []
        actual_set = set(actual_nodes)

        # Check required nodes
        required_failures = self._check_required_nodes(
            constraint.required_nodes, actual_set
        )
        failures.extend(required_failures)

        # Check forbidden nodes
        forbidden_failures = self._check_forbidden_nodes(
            constraint.forbidden_nodes, actual_set
        )
        failures.extend(forbidden_failures)

        # Check loop count
        if constraint.max_loops is not None:
            loop_failures = self._check_loop_count(
                constraint.max_loops, actual_nodes
            )
            failures.extend(loop_failures)

        # Calculate score
        total_checks = (
            len(constraint.required_nodes)
            + len(constraint.forbidden_nodes)
            + (1 if constraint.max_loops is not None else 0)
        )

        if total_checks == 0:
            score = 1.0
        else:
            passed_checks = total_checks - len(failures)
            score = max(0.0, passed_checks / total_checks)

        details = {
            "actual_nodes": actual_nodes,
            "unique_nodes_visited": list(actual_set),
            "required_nodes": constraint.required_nodes,
            "forbidden_nodes": constraint.forbidden_nodes,
            "max_loops": constraint.max_loops,
        }

        return EvaluationResult(
            passed=len(failures) == 0,
            score=score,
            failures=failures,
            details=details,
        )

    def _check_required_nodes(
        self, required: list[str], actual_set: set[str]
    ) -> list[str]:
        """Check that all required nodes were visited.

        Args:
            required: List of required node names
            actual_set: Set of actually visited nodes

        Returns:
            List of failure messages for missing nodes
        """
        failures = []
        for node in required:
            if node not in actual_set:
                failures.append(f"Required node '{node}' was not visited")
        return failures

    def _check_forbidden_nodes(
        self, forbidden: list[str], actual_set: set[str]
    ) -> list[str]:
        """Check that no forbidden nodes were visited.

        Args:
            forbidden: List of forbidden node names
            actual_set: Set of actually visited nodes

        Returns:
            List of failure messages for visited forbidden nodes
        """
        failures = []
        for node in forbidden:
            if node in actual_set:
                failures.append(f"Forbidden node '{node}' was visited")
        return failures

    def _check_loop_count(
        self, max_loops: int, actual_nodes: list[str]
    ) -> list[str]:
        """Check that loop count is within limits.

        A loop is detected when a node appears more than once in the sequence.
        The loop count for a node is (occurrences - 1).

        Args:
            max_loops: Maximum allowed loops for any single node
            actual_nodes: The actual sequence of nodes visited

        Returns:
            List of failure messages for nodes exceeding loop limit
        """
        failures = []
        node_counts = Counter(actual_nodes)

        for node, count in node_counts.items():
            loops = count - 1
            if loops > max_loops:
                failures.append(
                    f"Node '{node}' looped {loops} times, max allowed is {max_loops}"
                )

        return failures
