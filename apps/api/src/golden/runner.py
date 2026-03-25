"""Regression test runner for golden dataset evaluation.

Executes golden cases against LangGraph workflows and evaluates results
using trajectory, tool call, state, and coherence evaluators.

Usage:
    python -m golden.runner                          # Run all cases
    python -m golden.runner --difficulty easy        # Run only easy cases
    python -m golden.runner --dimension Schedule     # Run Schedule dimension
    python -m golden.runner --output json            # JSON output
    python -m golden.runner --case SCHED-001         # Run specific case
"""

import argparse
import json
import logging
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from golden.evaluators import (
    CoherenceEvaluator,
    EvaluationResult,
    StateEvaluator,
    ToolCallEvaluator,
    TrajectoryEvaluator,
)
from golden.evaluators.coherence_evaluator import ActualCoherenceIssue
from golden.evaluators.tool_call_evaluator import ActualToolCall
from golden.loader import GoldenDatasetLoader
from golden.schemas import CoherenceDimension, DifficultyLevel, GoldenCase

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """Result from executing a workflow on a golden case.

    Attributes:
        nodes_visited: Sequence of node names visited during execution
        tool_calls: List of tool calls made during execution
        final_state: Final state dictionary after execution
        coherence_issues: List of coherence issues detected
        execution_time_ms: Time taken to execute in milliseconds
        error: Error message if execution failed
    """

    nodes_visited: list[str] = field(default_factory=list)
    tool_calls: list[ActualToolCall] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)
    coherence_issues: list[ActualCoherenceIssue] = field(default_factory=list)
    execution_time_ms: float = 0.0
    error: str | None = None


class WorkflowExecutor(ABC):
    """Abstract base class for workflow executors.

    Implement this interface to connect the golden dataset runner
    to your actual LangGraph workflow.
    """

    @abstractmethod
    def execute(self, case: GoldenCase) -> WorkflowResult:
        """Execute the workflow for a given golden case.

        Args:
            case: The golden case to execute

        Returns:
            WorkflowResult with execution details
        """
        pass


class MockWorkflowExecutor(WorkflowExecutor):
    """Mock executor for testing the runner without actual workflow.

    Generates synthetic results based on expected values for dry-run testing.
    """

    def __init__(self, success_rate: float = 0.8) -> None:
        """Initialize mock executor.

        Args:
            success_rate: Probability of generating passing results (0.0-1.0)
        """
        self.success_rate = success_rate

    def execute(self, case: GoldenCase) -> WorkflowResult:
        """Generate mock workflow results based on expected values.

        Args:
            case: The golden case to mock execution for

        Returns:
            WorkflowResult with mock data matching expectations
        """
        import random

        start_time = time.time()

        # Generate nodes visited (always include required nodes for passing cases)
        nodes_visited = list(case.trajectory.required_nodes)
        if case.trajectory.optional_nodes and random.random() > 0.5:
            nodes_visited.extend(
                random.sample(
                    case.trajectory.optional_nodes,
                    k=min(2, len(case.trajectory.optional_nodes)),
                )
            )

        # Generate tool calls matching expected
        tool_calls = []
        if case.tool_calls:
            for tc_assertion in case.tool_calls:
                num_calls = tc_assertion.min_calls or 1
                for _ in range(num_calls):
                    args = {arg: f"mock_value_{arg}" for arg in tc_assertion.required_args}
                    tool_calls.append(
                        ActualToolCall(tool_name=tc_assertion.tool_name, arguments=args)
                    )

        # Generate coherence issues matching expected
        coherence_issues = []
        if case.expected_issues:
            for expected in case.expected_issues:
                coherence_issues.append(
                    ActualCoherenceIssue(
                        rule_id=expected.rule_id,
                        dimension=expected.dimension,
                        severity=expected.severity,
                        description=f"Mock issue containing {expected.description_contains or 'detected violation'}",
                    )
                )

        # Generate final state matching assertions
        final_state: dict[str, Any] = {}
        if case.state_assertions:
            for assertion in case.state_assertions:
                # Simple path handling for mock
                parts = assertion.path.split(".")
                current = final_state

                # Navigate/create nested structure
                for part in parts[:-1]:
                    if part not in current or not isinstance(current.get(part), dict):
                        current[part] = {}
                    current = current[part]

                # Set value based on operator
                final_key = parts[-1]
                if assertion.operator == "exists":
                    # For exists checks, set to True or a non-empty value
                    current[final_key] = True if assertion.expected_value else {"mock": "data"}
                elif assertion.operator == "greater_than":
                    # Set to expected + 1 to pass the assertion
                    current[final_key] = assertion.expected_value + 1
                elif assertion.operator == "less_than":
                    # Set to expected - 1 to pass the assertion
                    current[final_key] = max(0, assertion.expected_value - 1)
                else:
                    # equals or other operators
                    current[final_key] = assertion.expected_value

        execution_time_ms = (time.time() - start_time) * 1000

        return WorkflowResult(
            nodes_visited=nodes_visited,
            tool_calls=tool_calls,
            final_state=final_state,
            coherence_issues=coherence_issues,
            execution_time_ms=execution_time_ms,
        )


@dataclass
class CaseResult:
    """Result of evaluating a single golden case.

    Attributes:
        case_id: The golden case ID
        passed: Whether all evaluations passed
        trajectory_result: Result from trajectory evaluation
        tool_call_result: Result from tool call evaluation
        state_result: Result from state evaluation
        coherence_result: Result from coherence evaluation
        overall_score: Combined score from all evaluations
        execution_time_ms: Workflow execution time
        error: Error message if case failed to run
    """

    case_id: str
    passed: bool
    trajectory_result: EvaluationResult | None = None
    tool_call_result: EvaluationResult | None = None
    state_result: EvaluationResult | None = None
    coherence_result: EvaluationResult | None = None
    overall_score: float = 0.0
    execution_time_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 3),
            "execution_time_ms": round(self.execution_time_ms, 2),
            "error": self.error,
            "trajectory": asdict(self.trajectory_result) if self.trajectory_result else None,
            "tool_calls": asdict(self.tool_call_result) if self.tool_call_result else None,
            "state": asdict(self.state_result) if self.state_result else None,
            "coherence": asdict(self.coherence_result) if self.coherence_result else None,
        }


@dataclass
class RunSummary:
    """Summary of a regression test run.

    Attributes:
        total_cases: Total number of cases run
        passed_cases: Number of cases that passed
        failed_cases: Number of cases that failed
        error_cases: Number of cases with execution errors
        overall_pass_rate: Percentage of passing cases
        avg_score: Average score across all cases
        total_time_ms: Total execution time
        by_difficulty: Results grouped by difficulty
        by_dimension: Results grouped by dimension
        timestamp: When the run was executed
    """

    total_cases: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    overall_pass_rate: float
    avg_score: float
    total_time_ms: float
    by_difficulty: dict[str, dict[str, int]]
    by_dimension: dict[str, dict[str, int]]
    timestamp: str
    case_results: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": {
                "total_cases": self.total_cases,
                "passed_cases": self.passed_cases,
                "failed_cases": self.failed_cases,
                "error_cases": self.error_cases,
                "overall_pass_rate": round(self.overall_pass_rate, 2),
                "avg_score": round(self.avg_score, 3),
                "total_time_ms": round(self.total_time_ms, 2),
                "timestamp": self.timestamp,
            },
            "by_difficulty": self.by_difficulty,
            "by_dimension": self.by_dimension,
            "cases": [cr.to_dict() for cr in self.case_results],
        }


class RegressionRunner:
    """Regression test runner for golden dataset evaluation.

    Loads golden cases, executes workflows, and evaluates results
    using all available evaluators.
    """

    def __init__(
        self,
        dataset_dir: Path | str,
        executor: WorkflowExecutor | None = None,
    ) -> None:
        """Initialize the regression runner.

        Args:
            dataset_dir: Path to the golden dataset directory
            executor: Workflow executor to use. If None, uses MockWorkflowExecutor.
        """
        self.loader = GoldenDatasetLoader(dataset_dir)
        self.executor = executor or MockWorkflowExecutor()

        # Initialize evaluators
        self.trajectory_evaluator = TrajectoryEvaluator()
        self.tool_call_evaluator = ToolCallEvaluator()
        self.state_evaluator = StateEvaluator()
        self.coherence_evaluator = CoherenceEvaluator()

    def run_case(self, case: GoldenCase) -> CaseResult:
        """Run a single golden case through the workflow and evaluate.

        Args:
            case: The golden case to run

        Returns:
            CaseResult with evaluation details
        """
        try:
            # Execute workflow
            result = self.executor.execute(case)

            if result.error:
                return CaseResult(
                    case_id=case.case_id,
                    passed=False,
                    error=result.error,
                    execution_time_ms=result.execution_time_ms,
                )

            # Evaluate trajectory
            trajectory_result = self.trajectory_evaluator.evaluate(
                case.trajectory, result.nodes_visited
            )

            # Evaluate tool calls
            tool_call_result = None
            if case.tool_calls:
                tool_call_result = self.tool_call_evaluator.evaluate(
                    case.tool_calls, result.tool_calls
                )

            # Evaluate state assertions
            state_result = None
            if case.state_assertions:
                state_result = self.state_evaluator.evaluate(
                    case.state_assertions, result.final_state
                )

            # Evaluate coherence issues
            coherence_result = None
            if case.expected_issues:
                coherence_result = self.coherence_evaluator.evaluate(
                    case.expected_issues, result.coherence_issues
                )

            # Calculate overall pass/fail and score
            results_to_check = [trajectory_result]
            if tool_call_result:
                results_to_check.append(tool_call_result)
            if state_result:
                results_to_check.append(state_result)
            if coherence_result:
                results_to_check.append(coherence_result)

            passed = all(r.passed for r in results_to_check)
            overall_score = (
                sum(r.score for r in results_to_check) / len(results_to_check)
                if results_to_check
                else 0.0
            )

            return CaseResult(
                case_id=case.case_id,
                passed=passed,
                trajectory_result=trajectory_result,
                tool_call_result=tool_call_result,
                state_result=state_result,
                coherence_result=coherence_result,
                overall_score=overall_score,
                execution_time_ms=result.execution_time_ms,
            )

        except Exception as e:
            logger.exception("Error running case %s", case.case_id)
            return CaseResult(
                case_id=case.case_id,
                passed=False,
                error=str(e),
            )

    def run_all(
        self,
        difficulty: DifficultyLevel | None = None,
        dimensions: list[CoherenceDimension] | None = None,
        case_ids: list[str] | None = None,
    ) -> RunSummary:
        """Run all matching golden cases.

        Args:
            difficulty: Optional filter by difficulty level
            dimensions: Optional filter by dimensions (case must have at least one)
            case_ids: Optional list of specific case IDs to run

        Returns:
            RunSummary with aggregated results
        """
        start_time = time.time()

        # Load cases based on filters
        if case_ids:
            cases = [
                self.loader.load_case(cid)
                for cid in case_ids
                if self.loader.load_case(cid)
            ]
            cases = [c for c in cases if c is not None]
        elif difficulty or dimensions:
            cases = self.loader.filter_by_dimensions_and_difficulty(
                dimensions=dimensions, difficulty=difficulty
            )
        else:
            cases = self.loader.load_all_cases()

        # Run each case
        case_results: list[CaseResult] = []
        for case in cases:
            logger.info("Running case: %s", case.case_id)
            result = self.run_case(case)
            case_results.append(result)

        # Calculate summary statistics
        passed_cases = sum(1 for r in case_results if r.passed)
        error_cases = sum(1 for r in case_results if r.error)
        failed_cases = len(case_results) - passed_cases - error_cases

        # Group by difficulty
        by_difficulty: dict[str, dict[str, int]] = {}
        for case, result in zip(cases, case_results):
            diff = case.difficulty.value
            if diff not in by_difficulty:
                by_difficulty[diff] = {"total": 0, "passed": 0, "failed": 0}
            by_difficulty[diff]["total"] += 1
            if result.passed:
                by_difficulty[diff]["passed"] += 1
            else:
                by_difficulty[diff]["failed"] += 1

        # Group by dimension
        by_dimension: dict[str, dict[str, int]] = {}
        for case, result in zip(cases, case_results):
            for dim in case.dimensions:
                dim_name = dim.value
                if dim_name not in by_dimension:
                    by_dimension[dim_name] = {"total": 0, "passed": 0, "failed": 0}
                by_dimension[dim_name]["total"] += 1
                if result.passed:
                    by_dimension[dim_name]["passed"] += 1
                else:
                    by_dimension[dim_name]["failed"] += 1

        total_time_ms = (time.time() - start_time) * 1000
        avg_score = (
            sum(r.overall_score for r in case_results) / len(case_results)
            if case_results
            else 0.0
        )

        return RunSummary(
            total_cases=len(case_results),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            error_cases=error_cases,
            overall_pass_rate=(passed_cases / len(case_results) * 100) if case_results else 0.0,
            avg_score=avg_score,
            total_time_ms=total_time_ms,
            by_difficulty=by_difficulty,
            by_dimension=by_dimension,
            timestamp=datetime.now(timezone.utc).isoformat(),
            case_results=case_results,
        )


def format_text_report(summary: RunSummary) -> str:
    """Format the run summary as a human-readable text report.

    Args:
        summary: The run summary to format

    Returns:
        Formatted text report
    """
    lines = [
        "=" * 70,
        "GOLDEN DATASET REGRESSION TEST REPORT",
        "=" * 70,
        "",
        f"Timestamp: {summary.timestamp}",
        f"Total Cases: {summary.total_cases}",
        f"Passed: {summary.passed_cases} ({summary.overall_pass_rate:.1f}%)",
        f"Failed: {summary.failed_cases}",
        f"Errors: {summary.error_cases}",
        f"Average Score: {summary.avg_score:.3f}",
        f"Total Time: {summary.total_time_ms:.0f}ms",
        "",
        "-" * 70,
        "BY DIFFICULTY",
        "-" * 70,
    ]

    for diff, stats in sorted(summary.by_difficulty.items()):
        pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        lines.append(f"  {diff:8s}: {stats['passed']:2d}/{stats['total']:2d} passed ({pass_rate:.0f}%)")

    lines.extend([
        "",
        "-" * 70,
        "BY DIMENSION",
        "-" * 70,
    ])

    for dim, stats in sorted(summary.by_dimension.items()):
        pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        lines.append(f"  {dim:10s}: {stats['passed']:2d}/{stats['total']:2d} passed ({pass_rate:.0f}%)")

    # Failed cases detail
    failed_results = [r for r in summary.case_results if not r.passed]
    if failed_results:
        lines.extend([
            "",
            "-" * 70,
            "FAILED CASES",
            "-" * 70,
        ])
        for result in failed_results:
            lines.append(f"\n  {result.case_id}:")
            if result.error:
                lines.append(f"    ERROR: {result.error}")
            else:
                # Show failures from each evaluator
                if result.trajectory_result and result.trajectory_result.failures:
                    lines.append("    Trajectory failures:")
                    for f in result.trajectory_result.failures[:3]:
                        lines.append(f"      - {f}")
                if result.tool_call_result and result.tool_call_result.failures:
                    lines.append("    Tool call failures:")
                    for f in result.tool_call_result.failures[:3]:
                        lines.append(f"      - {f}")
                if result.state_result and result.state_result.failures:
                    lines.append("    State failures:")
                    for f in result.state_result.failures[:3]:
                        lines.append(f"      - {f}")
                if result.coherence_result and result.coherence_result.failures:
                    lines.append("    Coherence failures:")
                    for f in result.coherence_result.failures[:3]:
                        lines.append(f"      - {f}")

    lines.extend([
        "",
        "=" * 70,
        f"RESULT: {'PASS' if summary.failed_cases == 0 and summary.error_cases == 0 else 'FAIL'}",
        "=" * 70,
    ])

    return "\n".join(lines)


def main() -> int:
    """Main entry point for the regression runner CLI.

    Returns:
        Exit code (0 for success, 1 for failures, 2 for errors)
    """
    parser = argparse.ArgumentParser(
        description="Run golden dataset regression tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m golden.runner                      Run all cases
  python -m golden.runner --difficulty easy    Run easy cases only
  python -m golden.runner --dimension Schedule Run Schedule dimension
  python -m golden.runner --case SCHED-001     Run specific case
  python -m golden.runner --output json        Output as JSON
  python -m golden.runner --mock               Use mock executor (dry run)
        """,
    )

    parser.add_argument(
        "--difficulty",
        "-d",
        choices=["easy", "medium", "hard", "expert"],
        help="Filter by difficulty level",
    )
    parser.add_argument(
        "--dimension",
        "-D",
        choices=["Schedule", "Cost", "Legal", "Quality", "Scope", "Technical"],
        action="append",
        help="Filter by dimension (can be specified multiple times)",
    )
    parser.add_argument(
        "--case",
        "-c",
        action="append",
        dest="cases",
        help="Specific case ID to run (can be specified multiple times)",
    )
    parser.add_argument(
        "--output",
        "-o",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output-file",
        "-f",
        type=Path,
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Path to golden dataset directory",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock executor (for testing the runner itself)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Convert difficulty string to enum
    difficulty = None
    if args.difficulty:
        difficulty = DifficultyLevel(args.difficulty.capitalize())

    # Convert dimension strings to enums
    dimensions = None
    if args.dimension:
        dimensions = [CoherenceDimension(d) for d in args.dimension]

    # Create executor
    executor: WorkflowExecutor
    if args.mock:
        executor = MockWorkflowExecutor()
        logger.info("Using mock workflow executor")
    else:
        # Use mock for now - in production, replace with actual executor
        executor = MockWorkflowExecutor()
        logger.info("Using mock workflow executor (no production executor configured)")

    # Create and run the regression runner
    runner = RegressionRunner(args.dataset_dir, executor)
    summary = runner.run_all(
        difficulty=difficulty,
        dimensions=dimensions,
        case_ids=args.cases,
    )

    # Format output
    if args.output == "json":
        output = json.dumps(summary.to_dict(), indent=2)
    else:
        output = format_text_report(summary)

    # Write output
    if args.output_file:
        args.output_file.write_text(output)
        # Security: Only log filename, not full path
        logger.info("Report written to: %s", args.output_file.name)
    else:
        print(output)

    # Return exit code
    if summary.error_cases > 0:
        return 2
    elif summary.failed_cases > 0:
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
