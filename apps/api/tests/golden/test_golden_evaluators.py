"""Tests for golden dataset evaluators."""

import pytest
from golden.evaluators.base import EvaluationResult
from golden.evaluators.coherence_evaluator import ActualCoherenceIssue, CoherenceEvaluator
from golden.evaluators.state_evaluator import StateEvaluator
from golden.evaluators.tool_call_evaluator import ActualToolCall, ToolCallEvaluator
from golden.evaluators.trajectory_evaluator import TrajectoryEvaluator
from golden.schemas import (
    CoherenceDimension,
    CoherenceIssueAssertion,
    StateAssertion,
    ToolCallAssertion,
    TrajectoryConstraint,
)


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_success_factory(self) -> None:
        """Test creating a success result."""
        result = EvaluationResult.success(score=0.95)
        assert result.passed is True
        assert result.score == 0.95
        assert result.failures == []

    def test_failure_factory(self) -> None:
        """Test creating a failure result."""
        result = EvaluationResult.failure(
            failures=["Error 1", "Error 2"], score=0.3
        )
        assert result.passed is False
        assert result.score == 0.3
        assert len(result.failures) == 2

    def test_score_validation(self) -> None:
        """Test that score must be between 0 and 1."""
        with pytest.raises(ValueError):
            EvaluationResult(passed=True, score=1.5, failures=[])

        with pytest.raises(ValueError):
            EvaluationResult(passed=True, score=-0.1, failures=[])

    def test_merge_results(self) -> None:
        """Test merging two evaluation results."""
        result1 = EvaluationResult.success(score=0.8, details={"check1": True})
        result2 = EvaluationResult.failure(
            failures=["Error"], score=0.6, details={"check2": False}
        )

        merged = result1.merge(result2)

        assert merged.passed is False  # One failure means merged fails
        assert merged.score == 0.7  # Average of 0.8 and 0.6
        assert "Error" in merged.failures
        assert merged.details == {"check1": True, "check2": False}


class TestTrajectoryEvaluator:
    """Tests for TrajectoryEvaluator."""

    def test_all_required_nodes_visited(self) -> None:
        """Test passing when all required nodes are visited."""
        evaluator = TrajectoryEvaluator()
        constraint = TrajectoryConstraint(
            required_nodes=["loader", "analyzer", "reporter"]
        )
        actual = ["loader", "analyzer", "reporter"]

        result = evaluator.evaluate(constraint, actual)

        assert result.passed is True
        assert result.score == 1.0

    def test_missing_required_node(self) -> None:
        """Test failure when a required node is not visited."""
        evaluator = TrajectoryEvaluator()
        constraint = TrajectoryConstraint(
            required_nodes=["loader", "analyzer", "reporter"]
        )
        actual = ["loader", "analyzer"]  # Missing reporter

        result = evaluator.evaluate(constraint, actual)

        assert result.passed is False
        assert "reporter" in result.failures[0]

    def test_forbidden_node_visited(self) -> None:
        """Test failure when a forbidden node is visited."""
        evaluator = TrajectoryEvaluator()
        constraint = TrajectoryConstraint(
            required_nodes=["loader"],
            forbidden_nodes=["debug_node"],
        )
        actual = ["loader", "debug_node"]

        result = evaluator.evaluate(constraint, actual)

        assert result.passed is False
        assert "debug_node" in result.failures[0]

    def test_loop_count_exceeded(self) -> None:
        """Test failure when loop count exceeds maximum."""
        evaluator = TrajectoryEvaluator()
        constraint = TrajectoryConstraint(
            required_nodes=["analyzer"],
            max_loops=2,
        )
        actual = ["analyzer", "analyzer", "analyzer", "analyzer"]  # 3 loops

        result = evaluator.evaluate(constraint, actual)

        assert result.passed is False
        assert "looped" in result.failures[0].lower()

    def test_loop_count_within_limit(self) -> None:
        """Test passing when loop count is within limit."""
        evaluator = TrajectoryEvaluator()
        constraint = TrajectoryConstraint(
            required_nodes=["analyzer"],
            max_loops=3,
        )
        actual = ["analyzer", "analyzer", "analyzer"]  # 2 loops, within limit

        result = evaluator.evaluate(constraint, actual)

        assert result.passed is True

    def test_optional_nodes_allowed(self) -> None:
        """Test that optional nodes don't affect pass/fail."""
        evaluator = TrajectoryEvaluator()
        constraint = TrajectoryConstraint(
            required_nodes=["loader"],
            optional_nodes=["cache_check"],
        )

        # Without optional
        result1 = evaluator.evaluate(constraint, ["loader"])
        assert result1.passed is True

        # With optional
        result2 = evaluator.evaluate(constraint, ["loader", "cache_check"])
        assert result2.passed is True


class TestToolCallEvaluator:
    """Tests for ToolCallEvaluator."""

    def test_all_assertions_pass(
        self, sample_actual_tool_calls: list[ActualToolCall]
    ) -> None:
        """Test passing when all tool call assertions are satisfied."""
        evaluator = ToolCallEvaluator()
        assertions = [
            ToolCallAssertion(
                tool_name="extract_dates",
                required_args=["document_path"],
                min_calls=1,
                max_calls=5,
            )
        ]

        result = evaluator.evaluate(assertions, sample_actual_tool_calls)

        assert result.passed is True
        assert result.score == 1.0

    def test_tool_not_called_enough(self) -> None:
        """Test failure when tool not called minimum times."""
        evaluator = ToolCallEvaluator()
        assertions = [
            ToolCallAssertion(
                tool_name="extract_dates",
                min_calls=5,  # Require 5 calls
            )
        ]
        actual_calls = [
            ActualToolCall(tool_name="extract_dates", arguments={})
        ]

        result = evaluator.evaluate(assertions, actual_calls)

        assert result.passed is False
        assert "1 times" in result.failures[0]
        assert "minimum required is 5" in result.failures[0]

    def test_tool_called_too_many_times(self) -> None:
        """Test failure when tool called more than max times."""
        evaluator = ToolCallEvaluator()
        assertions = [
            ToolCallAssertion(
                tool_name="extract_dates",
                min_calls=1,
                max_calls=2,
            )
        ]
        actual_calls = [
            ActualToolCall(tool_name="extract_dates", arguments={})
            for _ in range(5)
        ]

        result = evaluator.evaluate(assertions, actual_calls)

        assert result.passed is False
        assert "5 times" in result.failures[0]
        assert "maximum allowed is 2" in result.failures[0]

    def test_missing_required_argument(self) -> None:
        """Test failure when required argument is missing."""
        evaluator = ToolCallEvaluator()
        assertions = [
            ToolCallAssertion(
                tool_name="extract_dates",
                required_args=["document_path", "date_format"],
            )
        ]
        actual_calls = [
            ActualToolCall(
                tool_name="extract_dates",
                arguments={"document_path": "/path"},  # Missing date_format
            )
        ]

        result = evaluator.evaluate(assertions, actual_calls)

        assert result.passed is False
        assert "date_format" in result.failures[0]

    def test_forbidden_argument_present(self) -> None:
        """Test failure when forbidden argument is present."""
        evaluator = ToolCallEvaluator()
        assertions = [
            ToolCallAssertion(
                tool_name="extract_dates",
                forbidden_args=["debug_mode"],
            )
        ]
        actual_calls = [
            ActualToolCall(
                tool_name="extract_dates",
                arguments={"debug_mode": True},
            )
        ]

        result = evaluator.evaluate(assertions, actual_calls)

        assert result.passed is False
        assert "debug_mode" in result.failures[0]

    def test_empty_assertions_pass(self) -> None:
        """Test that empty assertions always pass."""
        evaluator = ToolCallEvaluator()
        result = evaluator.evaluate([], [])

        assert result.passed is True
        assert result.score == 1.0


class TestStateEvaluator:
    """Tests for StateEvaluator."""

    def test_equals_operator_pass(self) -> None:
        """Test equals operator when values match."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="status",
                operator="equals",
                expected_value="completed",
            )
        ]
        state = {"status": "completed"}

        result = evaluator.evaluate(assertions, state)

        assert result.passed is True

    def test_equals_operator_fail(self) -> None:
        """Test equals operator when values don't match."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="status",
                operator="equals",
                expected_value="completed",
            )
        ]
        state = {"status": "pending"}

        result = evaluator.evaluate(assertions, state)

        assert result.passed is False

    def test_contains_operator_string(self) -> None:
        """Test contains operator with string."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="message",
                operator="contains",
                expected_value="error",
            )
        ]
        state = {"message": "An error occurred"}

        result = evaluator.evaluate(assertions, state)

        assert result.passed is True

    def test_contains_operator_list(self) -> None:
        """Test contains operator with list."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="tags",
                operator="contains",
                expected_value="urgent",
            )
        ]
        state = {"tags": ["urgent", "review"]}

        result = evaluator.evaluate(assertions, state)

        assert result.passed is True

    def test_greater_than_operator(self) -> None:
        """Test greater_than operator."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="count",
                operator="greater_than",
                expected_value=5,
            )
        ]

        result_pass = evaluator.evaluate(assertions, {"count": 10})
        assert result_pass.passed is True

        result_fail = evaluator.evaluate(assertions, {"count": 3})
        assert result_fail.passed is False

    def test_less_than_operator(self) -> None:
        """Test less_than operator."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="error_rate",
                operator="less_than",
                expected_value=0.1,
            )
        ]

        result_pass = evaluator.evaluate(assertions, {"error_rate": 0.05})
        assert result_pass.passed is True

        result_fail = evaluator.evaluate(assertions, {"error_rate": 0.2})
        assert result_fail.passed is False

    def test_exists_operator(self) -> None:
        """Test exists operator."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="optional_field",
                operator="exists",
                expected_value=True,
            )
        ]

        result_exists = evaluator.evaluate(
            assertions, {"optional_field": "value"}
        )
        assert result_exists.passed is True

        result_missing = evaluator.evaluate(assertions, {})
        assert result_missing.passed is False

    def test_nested_path(self) -> None:
        """Test accessing nested values with dot notation."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="issues.0.severity",
                operator="equals",
                expected_value="high",
            )
        ]
        state = {"issues": [{"severity": "high"}, {"severity": "low"}]}

        result = evaluator.evaluate(assertions, state)

        assert result.passed is True

    def test_at_node_assertion(self) -> None:
        """Test assertions at specific nodes."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="status",
                operator="equals",
                expected_value="analyzing",
                at_node="analyzer",
            )
        ]
        node_states = {
            "loader": {"status": "loading"},
            "analyzer": {"status": "analyzing"},
        }

        result = evaluator.evaluate(assertions, {}, node_states)

        assert result.passed is True

    def test_missing_path(self) -> None:
        """Test handling of non-existent paths."""
        evaluator = StateEvaluator()
        assertions = [
            StateAssertion(
                path="nonexistent.path",
                operator="equals",
                expected_value="value",
            )
        ]

        result = evaluator.evaluate(assertions, {})

        assert result.passed is False
        assert "does not exist" in result.failures[0]


class TestCoherenceEvaluator:
    """Tests for CoherenceEvaluator."""

    def test_all_issues_detected(
        self, sample_actual_coherence_issues: list[ActualCoherenceIssue]
    ) -> None:
        """Test passing when all expected issues are detected."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="SCHED-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
            )
        ]

        result = evaluator.evaluate(expected, sample_actual_coherence_issues)

        assert result.passed is True
        assert result.details["true_positives"] == 1

    def test_missing_expected_issue(self) -> None:
        """Test failure when expected issue is not detected."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="MISSING-001",
                dimension=CoherenceDimension.Legal,
                severity="high",
            )
        ]
        actual: list[ActualCoherenceIssue] = []

        result = evaluator.evaluate(expected, actual)

        assert result.passed is False
        assert "MISSING-001" in result.failures[0]

    def test_dimension_mismatch(self) -> None:
        """Test failure when detected issue has wrong dimension."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Schedule,  # Expected Schedule
                severity="high",
            )
        ]
        actual = [
            ActualCoherenceIssue(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Cost,  # But got Cost
                severity="high",
                description="Test issue",
            )
        ]

        result = evaluator.evaluate(expected, actual)

        assert result.passed is False
        assert "dimension" in result.failures[0].lower()

    def test_severity_mismatch(self) -> None:
        """Test failure when detected issue has wrong severity."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",  # Expected high
            )
        ]
        actual = [
            ActualCoherenceIssue(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Schedule,
                severity="low",  # But got low
                description="Test issue",
            )
        ]

        result = evaluator.evaluate(expected, actual)

        assert result.passed is False
        assert "severity" in result.failures[0].lower()

    def test_description_contains(self) -> None:
        """Test description_contains validation."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description_contains="milestone",
            )
        ]

        actual_match = [
            ActualCoherenceIssue(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description="The milestone date is incorrect",
            )
        ]
        result_match = evaluator.evaluate(expected, actual_match)
        assert result_match.passed is True

        actual_no_match = [
            ActualCoherenceIssue(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description="The deadline is incorrect",  # No "milestone"
            )
        ]
        result_no_match = evaluator.evaluate(expected, actual_no_match)
        assert result_no_match.passed is False

    def test_strict_mode_false_positives(self) -> None:
        """Test strict mode fails on unexpected issues."""
        evaluator = CoherenceEvaluator()
        expected: list[CoherenceIssueAssertion] = []  # Expect no issues
        actual = [
            ActualCoherenceIssue(
                rule_id="UNEXPECTED-001",
                dimension=CoherenceDimension.Cost,
                severity="medium",
                description="Unexpected issue",
            )
        ]

        # Non-strict mode passes (ignores false positives)
        result_non_strict = evaluator.evaluate(expected, actual, strict=False)
        assert result_non_strict.passed is True

        # Strict mode fails on unexpected issues
        result_strict = evaluator.evaluate(expected, actual, strict=True)
        assert result_strict.passed is False
        assert "Unexpected" in result_strict.failures[0]

    def test_precision_recall_metrics(self) -> None:
        """Test precision and recall calculation."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="FOUND-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
            ),
            CoherenceIssueAssertion(
                rule_id="MISSED-001",
                dimension=CoherenceDimension.Cost,
                severity="medium",
            ),
        ]
        actual = [
            ActualCoherenceIssue(
                rule_id="FOUND-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description="Found issue",
            ),
        ]

        result = evaluator.evaluate(expected, actual)

        # 1 true positive, 1 false negative, 0 false positives
        assert result.details["true_positives"] == 1
        assert result.details["false_negatives"] == 1
        assert result.details["recall"] == 0.5  # 1/(1+1)

    def test_evaluate_by_dimension(
        self, sample_actual_coherence_issues: list[ActualCoherenceIssue]
    ) -> None:
        """Test evaluation grouped by dimension."""
        evaluator = CoherenceEvaluator()
        expected = [
            CoherenceIssueAssertion(
                rule_id="SCHED-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
            ),
            CoherenceIssueAssertion(
                rule_id="COST-002",
                dimension=CoherenceDimension.Cost,
                severity="medium",
            ),
        ]

        results = evaluator.evaluate_by_dimension(
            expected, sample_actual_coherence_issues
        )

        assert "Schedule" in results
        assert "Cost" in results
        assert results["Schedule"].passed is True
        assert results["Cost"].passed is True
