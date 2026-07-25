"""TS-UD-GOLD-EVAL-001: Unit tests for golden dataset evaluators."""
from __future__ import annotations

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
    def test_success_factory(self) -> None:
        r = EvaluationResult.success(0.9)
        assert r.passed is True
        assert r.score == 0.9
        assert r.failures == []

    def test_failure_factory(self) -> None:
        r = EvaluationResult.failure(["bad"], 0.2)
        assert r.passed is False
        assert r.score == 0.2
        assert r.failures == ["bad"]

    def test_merge_both_pass(self) -> None:
        a = EvaluationResult(passed=True, score=1.0)
        b = EvaluationResult(passed=True, score=0.8)
        merged = a.merge(b)
        assert merged.passed is True
        assert merged.score == pytest.approx(0.9)

    def test_merge_one_fails(self) -> None:
        a = EvaluationResult(passed=True, score=1.0)
        b = EvaluationResult(passed=False, score=0.0, failures=["x"])
        merged = a.merge(b)
        assert merged.passed is False
        assert "x" in merged.failures

    def test_score_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="Score must be between"):
            EvaluationResult(passed=True, score=1.5)

    def test_merge_details_combined(self) -> None:
        a = EvaluationResult(passed=True, score=1.0, details={"a": 1})
        b = EvaluationResult(passed=True, score=0.8, details={"b": 2})
        merged = a.merge(b)
        assert merged.details == {"a": 1, "b": 2}


class TestTrajectoryEvaluator:
    def test_all_required_visited(self) -> None:
        constraint = TrajectoryConstraint(required_nodes=["A", "B"])
        result = TrajectoryEvaluator().evaluate(constraint, ["A", "B", "C"])
        assert result.passed is True
        assert result.score == 1.0

    def test_missing_required_node(self) -> None:
        constraint = TrajectoryConstraint(required_nodes=["A", "B"])
        result = TrajectoryEvaluator().evaluate(constraint, ["A"])
        assert result.passed is False
        assert any("B" in f for f in result.failures)

    def test_forbidden_node_visited(self) -> None:
        constraint = TrajectoryConstraint(
            required_nodes=["A"], forbidden_nodes=["X"]
        )
        result = TrajectoryEvaluator().evaluate(constraint, ["A", "X"])
        assert result.passed is False
        assert any("X" in f for f in result.failures)

    def test_no_forbidden_violations(self) -> None:
        constraint = TrajectoryConstraint(
            required_nodes=["A"], forbidden_nodes=["X"]
        )
        result = TrajectoryEvaluator().evaluate(constraint, ["A"])
        assert result.passed is True

    def test_max_loops_exceeded(self) -> None:
        constraint = TrajectoryConstraint(required_nodes=["A"], max_loops=1)
        result = TrajectoryEvaluator().evaluate(constraint, ["A", "A", "A"])
        assert result.passed is False
        assert any("looped" in f for f in result.failures)

    def test_max_loops_within_limit(self) -> None:
        constraint = TrajectoryConstraint(required_nodes=["A"], max_loops=2)
        result = TrajectoryEvaluator().evaluate(constraint, ["A", "A", "A"])
        assert result.passed is True

    def test_empty_constraints_score_one(self) -> None:
        constraint = TrajectoryConstraint(required_nodes=["A"])
        result = TrajectoryEvaluator().evaluate(constraint, [])
        assert result.passed is False
        assert result.score < 1.0


class TestToolCallEvaluator:
    def test_tool_called_with_required_args(self) -> None:
        assertion = ToolCallAssertion(
            tool_name="search", required_args=["query"]
        )
        actual = [ActualToolCall(tool_name="search", arguments={"query": "test"})]
        result = ToolCallEvaluator().evaluate([assertion], actual)
        assert result.passed is True

    def test_tool_not_called_enough(self) -> None:
        assertion = ToolCallAssertion(tool_name="search", min_calls=2)
        actual = [ActualToolCall(tool_name="search", arguments={})]
        result = ToolCallEvaluator().evaluate([assertion], actual)
        assert result.passed is False
        assert any("minimum" in f for f in result.failures)

    def test_tool_exceeds_max_calls(self) -> None:
        assertion = ToolCallAssertion(tool_name="search", max_calls=1)
        actual = [
            ActualToolCall(tool_name="search", arguments={}),
            ActualToolCall(tool_name="search", arguments={}),
        ]
        result = ToolCallEvaluator().evaluate([assertion], actual)
        assert result.passed is False
        assert any("maximum" in f for f in result.failures)

    def test_missing_required_arg(self) -> None:
        assertion = ToolCallAssertion(
            tool_name="db", required_args=["query", "limit"]
        )
        actual = [ActualToolCall(tool_name="db", arguments={"query": "SELECT"})]
        result = ToolCallEvaluator().evaluate([assertion], actual)
        assert result.passed is False
        assert any("limit" in f for f in result.failures)

    def test_forbidden_arg_present(self) -> None:
        assertion = ToolCallAssertion(
            tool_name="db", forbidden_args=["password"]
        )
        actual = [
            ActualToolCall(
                tool_name="db", arguments={"query": "SELECT", "password": "secret"}
            )
        ]
        result = ToolCallEvaluator().evaluate([assertion], actual)
        assert result.passed is False
        assert any("password" in f for f in result.failures)

    def test_no_assertions_passes(self) -> None:
        result = ToolCallEvaluator().evaluate([], [])
        assert result.passed is True
        assert result.score == 1.0


class TestStateEvaluator:
    def test_equals_match(self) -> None:
        assertion = StateAssertion(path="status", operator="equals", expected_value="ok")
        result = StateEvaluator().evaluate([assertion], {"status": "ok"})
        assert result.passed is True

    def test_equals_mismatch(self) -> None:
        assertion = StateAssertion(path="status", operator="equals", expected_value="ok")
        result = StateEvaluator().evaluate([assertion], {"status": "error"})
        assert result.passed is False

    def test_contains_match(self) -> None:
        assertion = StateAssertion(
            path="msg", operator="contains", expected_value="hello"
        )
        result = StateEvaluator().evaluate([assertion], {"msg": "hello world"})
        assert result.passed is True

    def test_greater_than(self) -> None:
        assertion = StateAssertion(
            path="score", operator="greater_than", expected_value=5
        )
        result = StateEvaluator().evaluate([assertion], {"score": 10})
        assert result.passed is True

    def test_less_than(self) -> None:
        assertion = StateAssertion(
            path="count", operator="less_than", expected_value=100
        )
        result = StateEvaluator().evaluate([assertion], {"count": 50})
        assert result.passed is True

    def test_exists_true(self) -> None:
        assertion = StateAssertion(
            path="data", operator="exists", expected_value=True
        )
        result = StateEvaluator().evaluate([assertion], {"data": [1]})
        assert result.passed is True

    def test_exists_false(self) -> None:
        assertion = StateAssertion(
            path="missing", operator="exists", expected_value=False
        )
        result = StateEvaluator().evaluate([assertion], {"other": 1})
        assert result.passed is True

    def test_nested_path(self) -> None:
        assertion = StateAssertion(
            path="a.b.c", operator="equals", expected_value=42
        )
        result = StateEvaluator().evaluate([assertion], {"a": {"b": {"c": 42}}})
        assert result.passed is True

    def test_array_index_path(self) -> None:
        assertion = StateAssertion(
            path="items.0", operator="equals", expected_value="first"
        )
        result = StateEvaluator().evaluate(
            [assertion], {"items": ["first", "second"]}
        )
        assert result.passed is True

    def test_missing_path(self) -> None:
        assertion = StateAssertion(
            path="nope.x", operator="equals", expected_value=1
        )
        result = StateEvaluator().evaluate([assertion], {"other": 1})
        assert result.passed is False

    def test_empty_assertions(self) -> None:
        result = StateEvaluator().evaluate([], {})
        assert result.passed is True
        assert result.score == 1.0


class TestCoherenceEvaluator:
    def test_matching_issue(self) -> None:
        expected = CoherenceIssueAssertion(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
        )
        actual = [
            ActualCoherenceIssue(
                rule_id="SCHED-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description="Schedule delay detected",
            )
        ]
        result = CoherenceEvaluator().evaluate([expected], actual)
        assert result.passed is True

    def test_missing_expected_issue(self) -> None:
        expected = CoherenceIssueAssertion(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
        )
        result = CoherenceEvaluator().evaluate([expected], [])
        assert result.passed is False
        assert any("not detected" in f for f in result.failures)

    def test_wrong_dimension(self) -> None:
        expected = CoherenceIssueAssertion(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
        )
        actual = [
            ActualCoherenceIssue(
                rule_id="SCHED-001",
                dimension=CoherenceDimension.Cost,
                severity="high",
                description="x",
            )
        ]
        result = CoherenceEvaluator().evaluate([expected], actual)
        assert result.passed is False

    def test_description_contains(self) -> None:
        expected = CoherenceIssueAssertion(
            rule_id="COST-001",
            dimension=CoherenceDimension.Cost,
            severity="medium",
            description_contains="budget",
        )
        actual = [
            ActualCoherenceIssue(
                rule_id="COST-001",
                dimension=CoherenceDimension.Cost,
                severity="medium",
                description="Budget overrun detected",
            )
        ]
        result = CoherenceEvaluator().evaluate([expected], actual)
        assert result.passed is True

    def test_strict_mode_fails_on_extra(self) -> None:
        expected = CoherenceIssueAssertion(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
        )
        actual = [
            ActualCoherenceIssue(
                rule_id="SCHED-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description="x",
            ),
            ActualCoherenceIssue(
                rule_id="SCHED-002",
                dimension=CoherenceDimension.Schedule,
                severity="low",
                description="y",
            ),
        ]
        result = CoherenceEvaluator().evaluate([expected], actual, strict=True)
        assert result.passed is False
        assert any("Unexpected" in f for f in result.failures)

    def test_empty_both(self) -> None:
        result = CoherenceEvaluator().evaluate([], [])
        assert result.passed is True

    def test_evaluate_by_dimension(self) -> None:
        expected = CoherenceIssueAssertion(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
        )
        actual = [
            ActualCoherenceIssue(
                rule_id="SCHED-001",
                dimension=CoherenceDimension.Schedule,
                severity="high",
                description="x",
            )
        ]
        results = CoherenceEvaluator().evaluate_by_dimension([expected], actual)
        assert "Schedule" in results
        assert results["Schedule"].passed is True
