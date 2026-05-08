"""Tests for golden dataset regression runner."""

from pathlib import Path

from golden.evaluators.base import EvaluationResult
from golden.runner import (
    CaseResult,
    MockWorkflowExecutor,
    RegressionRunner,
    RunSummary,
    WorkflowResult,
    format_text_report,
)
from golden.schemas import (
    CoherenceDimension,
    DifficultyLevel,
    GoldenCase,
    InputDocuments,
    TrajectoryConstraint,
)


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are properly initialized."""
        result = WorkflowResult()
        assert result.nodes_visited == []
        assert result.tool_calls == []
        assert result.final_state == {}
        assert result.coherence_issues == []
        assert result.execution_time_ms == 0.0
        assert result.error is None


class TestMockWorkflowExecutor:
    """Tests for MockWorkflowExecutor."""

    def test_execute_generates_required_nodes(self) -> None:
        """Test that mock executor generates all required nodes."""
        case = GoldenCase(
            case_id="SCHED-001",
            name="Test case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(
                required_nodes=["node_a", "node_b", "node_c"]
            ),
        )

        executor = MockWorkflowExecutor()
        result = executor.execute(case)

        assert "node_a" in result.nodes_visited
        assert "node_b" in result.nodes_visited
        assert "node_c" in result.nodes_visited

    def test_execute_generates_coherence_issues(self) -> None:
        """Test that mock executor generates expected coherence issues."""
        from golden.schemas import CoherenceIssueAssertion

        case = GoldenCase(
            case_id="SCHED-001",
            name="Test case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
            expected_issues=[
                CoherenceIssueAssertion(
                    rule_id="SCHED-001",
                    dimension=CoherenceDimension.Schedule,
                    severity="high",
                    description_contains="milestone",
                )
            ],
        )

        executor = MockWorkflowExecutor()
        result = executor.execute(case)

        assert len(result.coherence_issues) == 1
        assert result.coherence_issues[0].rule_id == "SCHED-001"


class TestCaseResult:
    """Tests for CaseResult dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = CaseResult(
            case_id="TEST-001",
            passed=True,
            overall_score=0.95,
            execution_time_ms=100.5,
        )

        d = result.to_dict()
        assert d["case_id"] == "TEST-001"
        assert d["passed"] is True
        assert d["overall_score"] == 0.95
        assert d["execution_time_ms"] == 100.5

    def test_to_dict_with_evaluations(self) -> None:
        """Test to_dict includes evaluation results."""
        result = CaseResult(
            case_id="TEST-001",
            passed=True,
            trajectory_result=EvaluationResult.success(score=1.0),
            overall_score=1.0,
        )

        d = result.to_dict()
        assert d["trajectory"] is not None
        assert d["trajectory"]["passed"] is True


class TestRegressionRunner:
    """Tests for RegressionRunner."""

    def test_run_case_success(self) -> None:
        """Test running a single case successfully."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        runner = RegressionRunner(golden_dir, MockWorkflowExecutor())

        case = runner.loader.load_case("SCHED-001")
        assert case is not None

        result = runner.run_case(case)
        assert result.case_id == "SCHED-001"
        assert result.trajectory_result is not None

    def test_run_all_returns_summary(self) -> None:
        """Test run_all returns proper summary."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        runner = RegressionRunner(golden_dir, MockWorkflowExecutor())

        summary = runner.run_all()

        assert summary.total_cases == 100
        assert len(summary.case_results) == 100
        assert summary.timestamp is not None

    def test_run_all_with_difficulty_filter(self) -> None:
        """Test filtering by difficulty."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        runner = RegressionRunner(golden_dir, MockWorkflowExecutor())

        summary = runner.run_all(difficulty=DifficultyLevel.Easy)

        assert summary.total_cases == 20
        assert "Easy" in summary.by_difficulty
        assert summary.by_difficulty["Easy"]["total"] == 20

    def test_run_all_with_dimension_filter(self) -> None:
        """Test filtering by dimension."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        runner = RegressionRunner(golden_dir, MockWorkflowExecutor())

        summary = runner.run_all(dimensions=[CoherenceDimension.Legal])

        # All cases with Legal dimension
        assert summary.total_cases >= 5
        assert "Legal" in summary.by_dimension

    def test_run_all_with_case_ids(self) -> None:
        """Test running specific cases by ID."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        runner = RegressionRunner(golden_dir, MockWorkflowExecutor())

        summary = runner.run_all(case_ids=["SCHED-001", "COST-001"])

        assert summary.total_cases == 2
        case_ids = [r.case_id for r in summary.case_results]
        assert "SCHED-001" in case_ids
        assert "COST-001" in case_ids


class TestRunSummary:
    """Tests for RunSummary dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        summary = RunSummary(
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            error_cases=0,
            overall_pass_rate=80.0,
            avg_score=0.85,
            total_time_ms=1000.0,
            by_difficulty={"Easy": {"total": 5, "passed": 4, "failed": 1}},
            by_dimension={"Schedule": {"total": 3, "passed": 3, "failed": 0}},
            timestamp="2024-01-01T00:00:00Z",
        )

        d = summary.to_dict()
        assert d["summary"]["total_cases"] == 10
        assert d["summary"]["passed_cases"] == 8
        assert d["by_difficulty"]["Easy"]["total"] == 5


class TestFormatTextReport:
    """Tests for text report formatting."""

    def test_format_passing_report(self) -> None:
        """Test formatting a passing report."""
        summary = RunSummary(
            total_cases=5,
            passed_cases=5,
            failed_cases=0,
            error_cases=0,
            overall_pass_rate=100.0,
            avg_score=1.0,
            total_time_ms=100.0,
            by_difficulty={"Easy": {"total": 5, "passed": 5, "failed": 0}},
            by_dimension={"Schedule": {"total": 5, "passed": 5, "failed": 0}},
            timestamp="2024-01-01T00:00:00Z",
        )

        report = format_text_report(summary)

        assert "GOLDEN DATASET REGRESSION TEST REPORT" in report
        assert "Total Cases: 5" in report
        assert "Passed: 5 (100.0%)" in report
        assert "RESULT: PASS" in report

    def test_format_failing_report(self) -> None:
        """Test formatting a failing report."""
        summary = RunSummary(
            total_cases=5,
            passed_cases=3,
            failed_cases=2,
            error_cases=0,
            overall_pass_rate=60.0,
            avg_score=0.6,
            total_time_ms=100.0,
            by_difficulty={"Easy": {"total": 5, "passed": 3, "failed": 2}},
            by_dimension={"Schedule": {"total": 5, "passed": 3, "failed": 2}},
            timestamp="2024-01-01T00:00:00Z",
            case_results=[
                CaseResult(case_id="FAIL-001", passed=False, error="Test error"),
                CaseResult(case_id="FAIL-002", passed=False),
            ],
        )

        report = format_text_report(summary)

        assert "Failed: 2" in report
        assert "FAILED CASES" in report
        assert "FAIL-001" in report
        assert "RESULT: FAIL" in report
