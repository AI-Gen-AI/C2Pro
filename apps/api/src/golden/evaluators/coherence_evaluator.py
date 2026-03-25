"""Coherence issue evaluator for validating detected coherence violations.

Validates that the workflow correctly identifies expected coherence
issues with proper dimension, severity, and rule classification.
"""

from dataclasses import dataclass
from typing import Any

from golden.evaluators.base import EvaluationResult
from golden.schemas import CoherenceDimension, CoherenceIssueAssertion


@dataclass
class ActualCoherenceIssue:
    """Represents an actual coherence issue detected by the workflow.

    Attributes:
        rule_id: Unique identifier for the coherence rule
        dimension: Which coherence dimension this issue belongs to
        severity: Severity level (high, medium, low)
        description: Human-readable description of the issue
    """

    rule_id: str
    dimension: CoherenceDimension
    severity: str
    description: str


class CoherenceEvaluator:
    """Evaluator for coherence issue detection validation.

    Checks that:
    - Expected coherence issues were detected
    - Issues have correct dimensions and severities
    - Issue descriptions contain expected content
    - No false positives for critical rules
    """

    def evaluate(
        self,
        expected_issues: list[CoherenceIssueAssertion],
        actual_issues: list[ActualCoherenceIssue],
        strict: bool = False,
    ) -> EvaluationResult:
        """Evaluate detected coherence issues against expectations.

        Args:
            expected_issues: List of expected issue assertions
            actual_issues: List of actually detected issues
            strict: If True, fail on unexpected issues (false positives)

        Returns:
            EvaluationResult with pass/fail status and details
        """
        failures: list[str] = []
        matched_expected: set[str] = set()
        matched_actual: set[str] = set()

        # Check each expected issue
        for expected in expected_issues:
            match_result = self._find_matching_issue(expected, actual_issues)
            if match_result["matched"]:
                matched_expected.add(expected.rule_id)
                matched_actual.add(match_result["matched_rule_id"])
            else:
                failures.extend(match_result["failures"])

        # In strict mode, check for unexpected issues
        if strict:
            for actual in actual_issues:
                if actual.rule_id not in matched_actual:
                    failures.append(
                        f"Unexpected coherence issue detected: {actual.rule_id} "
                        f"({actual.dimension.value}, {actual.severity})"
                    )

        # Calculate metrics
        true_positives = len(matched_expected)
        false_negatives = len(expected_issues) - true_positives
        false_positives = len(actual_issues) - len(matched_actual) if strict else 0

        # Precision and recall
        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 1.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 1.0
        )

        # F1 score as overall metric
        f1_score = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        details = {
            "expected_count": len(expected_issues),
            "actual_count": len(actual_issues),
            "true_positives": true_positives,
            "false_negatives": false_negatives,
            "false_positives": false_positives if strict else "N/A (non-strict mode)",
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1_score, 3),
            "matched_rules": list(matched_expected),
        }

        return EvaluationResult(
            passed=len(failures) == 0,
            score=f1_score,
            failures=failures,
            details=details,
        )

    def _find_matching_issue(
        self,
        expected: CoherenceIssueAssertion,
        actual_issues: list[ActualCoherenceIssue],
    ) -> dict[str, Any]:
        """Find an actual issue matching the expected assertion.

        Args:
            expected: The expected issue assertion
            actual_issues: List of actual issues to search

        Returns:
            Dict with match status and any failures
        """
        # First, find issues with matching rule_id
        matching_by_rule = [
            issue for issue in actual_issues
            if issue.rule_id == expected.rule_id
        ]

        if not matching_by_rule:
            return {
                "matched": False,
                "matched_rule_id": None,
                "failures": [
                    f"Expected coherence issue '{expected.rule_id}' was not detected"
                ],
            }

        # Check dimension and severity for each matching issue
        failures: list[str] = []
        for issue in matching_by_rule:
            issue_failures = []

            # Check dimension
            if issue.dimension != expected.dimension:
                issue_failures.append(
                    f"Issue '{expected.rule_id}' has dimension "
                    f"'{issue.dimension.value}', expected '{expected.dimension.value}'"
                )

            # Check severity
            if issue.severity != expected.severity:
                issue_failures.append(
                    f"Issue '{expected.rule_id}' has severity "
                    f"'{issue.severity}', expected '{expected.severity}'"
                )

            # Check description if specified
            if expected.description_contains:
                if expected.description_contains.lower() not in issue.description.lower():
                    issue_failures.append(
                        f"Issue '{expected.rule_id}' description does not contain "
                        f"'{expected.description_contains}'"
                    )

            # If this issue has no failures, it's a match
            if not issue_failures:
                return {
                    "matched": True,
                    "matched_rule_id": issue.rule_id,
                    "failures": [],
                }

            failures.extend(issue_failures)

        # No perfect match found
        return {
            "matched": False,
            "matched_rule_id": None,
            "failures": failures[:1],  # Return first failure only to avoid noise
        }

    def evaluate_by_dimension(
        self,
        expected_issues: list[CoherenceIssueAssertion],
        actual_issues: list[ActualCoherenceIssue],
    ) -> dict[str, EvaluationResult]:
        """Evaluate coherence issues grouped by dimension.

        Args:
            expected_issues: List of expected issue assertions
            actual_issues: List of actually detected issues

        Returns:
            Dict mapping dimension name to EvaluationResult
        """
        results: dict[str, EvaluationResult] = {}

        for dimension in CoherenceDimension:
            dim_expected = [
                issue for issue in expected_issues
                if issue.dimension == dimension
            ]
            dim_actual = [
                issue for issue in actual_issues
                if issue.dimension == dimension
            ]

            if dim_expected or dim_actual:
                results[dimension.value] = self.evaluate(
                    dim_expected, dim_actual, strict=False
                )

        return results
