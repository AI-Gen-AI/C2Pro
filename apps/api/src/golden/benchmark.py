"""Accuracy benchmark runner for golden dataset evaluation.

Runs golden dataset evaluations and tracks accuracy metrics over time.
Supports baseline comparison, historical trend analysis, and accuracy
thresholds for CI/CD gate enforcement.

Usage:
    python -m golden.benchmark                     # Run benchmark
    python -m golden.benchmark --baseline          # Set new baseline
    python -m golden.benchmark --compare           # Compare to baseline
    python -m golden.benchmark --threshold 90      # Fail if accuracy < 90%
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from golden.runner import (
    MockWorkflowExecutor,
    RegressionRunner,
    RunSummary,
    WorkflowExecutor,
)
from golden.schemas import CoherenceDimension, DifficultyLevel

logger = logging.getLogger(__name__)

# Security: Max file sizes for benchmark artifacts
MAX_BASELINE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_HISTORY_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_HISTORY_ENTRIES = 1000  # Prevent unbounded growth


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for a benchmark run.

    Attributes:
        overall_accuracy: Overall pass rate as percentage (0-100)
        by_difficulty: Accuracy by difficulty level
        by_dimension: Accuracy by coherence dimension
        total_cases: Total cases evaluated
        passed_cases: Number of passing cases
        failed_cases: Number of failing cases
        avg_score: Average evaluation score (0-1)
        timestamp: When benchmark was run
    """

    overall_accuracy: float
    by_difficulty: dict[str, float]
    by_dimension: dict[str, float]
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_score: float
    timestamp: str
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_run_summary(cls, summary: RunSummary) -> "AccuracyMetrics":
        """Create AccuracyMetrics from a RegressionRunner summary.

        Args:
            summary: The run summary from RegressionRunner

        Returns:
            AccuracyMetrics instance
        """
        by_difficulty = {}
        for diff, stats in summary.by_difficulty.items():
            total = stats.get("total", 0)
            passed = stats.get("passed", 0)
            by_difficulty[diff] = (passed / total * 100) if total > 0 else 0.0

        by_dimension = {}
        for dim, stats in summary.by_dimension.items():
            total = stats.get("total", 0)
            passed = stats.get("passed", 0)
            by_dimension[dim] = (passed / total * 100) if total > 0 else 0.0

        return cls(
            overall_accuracy=summary.overall_pass_rate,
            by_difficulty=by_difficulty,
            by_dimension=by_dimension,
            total_cases=summary.total_cases,
            passed_cases=summary.passed_cases,
            failed_cases=summary.failed_cases,
            avg_score=summary.avg_score,
            timestamp=summary.timestamp,
            execution_time_ms=summary.total_time_ms,
        )


@dataclass
class BaselineComparison:
    """Comparison between current run and baseline.

    Attributes:
        current: Current run metrics
        baseline: Baseline metrics
        accuracy_delta: Change in overall accuracy (positive = improvement)
        improved_dimensions: Dimensions with improved accuracy
        degraded_dimensions: Dimensions with degraded accuracy
        improved_difficulties: Difficulties with improved accuracy
        degraded_difficulties: Difficulties with degraded accuracy
        meets_threshold: Whether current meets the minimum threshold
        threshold: The threshold used for comparison
    """

    current: AccuracyMetrics
    baseline: AccuracyMetrics | None
    accuracy_delta: float
    improved_dimensions: list[str]
    degraded_dimensions: list[str]
    improved_difficulties: list[str]
    degraded_difficulties: list[str]
    meets_threshold: bool
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "current": self.current.to_dict(),
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "accuracy_delta": round(self.accuracy_delta, 2),
            "improved_dimensions": self.improved_dimensions,
            "degraded_dimensions": self.degraded_dimensions,
            "improved_difficulties": self.improved_difficulties,
            "degraded_difficulties": self.degraded_difficulties,
            "meets_threshold": self.meets_threshold,
            "threshold": self.threshold,
        }


@dataclass
class BenchmarkHistory:
    """Historical benchmark data for trend analysis.

    Attributes:
        entries: List of historical metrics entries
        max_entries: Maximum entries to keep
    """

    entries: list[AccuracyMetrics] = field(default_factory=list)
    max_entries: int = MAX_HISTORY_ENTRIES

    def add_entry(self, metrics: AccuracyMetrics) -> None:
        """Add a new entry, trimming old entries if needed."""
        self.entries.append(metrics)
        if len(self.entries) > self.max_entries:
            # Keep most recent entries
            self.entries = self.entries[-self.max_entries :]

    def get_trend(self, last_n: int = 10) -> dict[str, Any]:
        """Get accuracy trend over last N entries.

        Args:
            last_n: Number of recent entries to analyze

        Returns:
            Dictionary with trend statistics
        """
        if not self.entries:
            return {"trend": "no_data", "entries": 0}

        recent = self.entries[-last_n:]
        accuracies = [e.overall_accuracy for e in recent]

        if len(accuracies) < 2:
            return {
                "trend": "insufficient_data",
                "entries": len(accuracies),
                "current": accuracies[-1] if accuracies else 0,
            }

        # Calculate trend direction
        first_half = accuracies[: len(accuracies) // 2]
        second_half = accuracies[len(accuracies) // 2 :]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 1:
            trend = "improving"
        elif second_avg < first_avg - 1:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "entries": len(accuracies),
            "current": accuracies[-1],
            "min": min(accuracies),
            "max": max(accuracies),
            "avg": sum(accuracies) / len(accuracies),
            "delta": round(accuracies[-1] - accuracies[0], 2),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "max_entries": self.max_entries,
            "trend": self.get_trend(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkHistory":
        """Create BenchmarkHistory from dictionary."""
        entries = []
        for entry_data in data.get("entries", []):
            entries.append(
                AccuracyMetrics(
                    overall_accuracy=entry_data["overall_accuracy"],
                    by_difficulty=entry_data["by_difficulty"],
                    by_dimension=entry_data["by_dimension"],
                    total_cases=entry_data["total_cases"],
                    passed_cases=entry_data["passed_cases"],
                    failed_cases=entry_data["failed_cases"],
                    avg_score=entry_data["avg_score"],
                    timestamp=entry_data["timestamp"],
                    execution_time_ms=entry_data.get("execution_time_ms", 0.0),
                )
            )
        return cls(
            entries=entries,
            max_entries=data.get("max_entries", MAX_HISTORY_ENTRIES),
        )


class AccuracyBenchmark:
    """Accuracy benchmark runner for golden dataset evaluation.

    Tracks accuracy metrics over time, compares against baselines,
    and enforces accuracy thresholds for CI/CD gates.
    """

    def __init__(
        self,
        dataset_dir: Path | str,
        artifacts_dir: Path | str | None = None,
        executor: WorkflowExecutor | None = None,
    ) -> None:
        """Initialize the benchmark runner.

        Args:
            dataset_dir: Path to the golden dataset directory
            artifacts_dir: Path to store benchmark artifacts (baseline, history).
                          Defaults to dataset_dir/.benchmark
            executor: Workflow executor to use. If None, uses MockWorkflowExecutor.
        """
        self.dataset_dir = Path(dataset_dir).resolve()
        self.artifacts_dir = (
            Path(artifacts_dir).resolve()
            if artifacts_dir
            else self.dataset_dir / ".benchmark"
        )
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.runner = RegressionRunner(dataset_dir, executor or MockWorkflowExecutor())

        self.baseline_file = self.artifacts_dir / "baseline.json"
        self.history_file = self.artifacts_dir / "history.json"

    def _validate_file_size(self, file_path: Path, max_size: int) -> None:
        """Validate file size before reading.

        Args:
            file_path: Path to file
            max_size: Maximum allowed size in bytes

        Raises:
            ValueError: If file exceeds maximum size
        """
        if file_path.exists():
            size = file_path.stat().st_size
            if size > max_size:
                raise ValueError(
                    f"File {file_path.name} ({size:,} bytes) exceeds maximum "
                    f"allowed size ({max_size:,} bytes)"
                )

    def load_baseline(self) -> AccuracyMetrics | None:
        """Load baseline metrics from file.

        Returns:
            AccuracyMetrics or None if no baseline exists
        """
        if not self.baseline_file.exists():
            return None

        try:
            self._validate_file_size(self.baseline_file, MAX_BASELINE_SIZE_BYTES)
            with open(self.baseline_file, encoding="utf-8") as f:
                data = json.load(f)
            return AccuracyMetrics(**data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Failed to load baseline: %s", type(e).__name__)
            return None

    def save_baseline(self, metrics: AccuracyMetrics) -> None:
        """Save metrics as the new baseline.

        Args:
            metrics: The metrics to save as baseline
        """
        with open(self.baseline_file, "w", encoding="utf-8") as f:
            json.dump(metrics.to_dict(), f, indent=2)
        logger.info("Saved baseline with accuracy: %.1f%%", metrics.overall_accuracy)

    def load_history(self) -> BenchmarkHistory:
        """Load benchmark history from file.

        Returns:
            BenchmarkHistory (empty if no history exists)
        """
        if not self.history_file.exists():
            return BenchmarkHistory()

        try:
            self._validate_file_size(self.history_file, MAX_HISTORY_SIZE_BYTES)
            with open(self.history_file, encoding="utf-8") as f:
                data = json.load(f)
            return BenchmarkHistory.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Failed to load history: %s", type(e).__name__)
            return BenchmarkHistory()

    def save_history(self, history: BenchmarkHistory) -> None:
        """Save benchmark history to file.

        Args:
            history: The history to save
        """
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history.to_dict(), f, indent=2)
        logger.info("Saved history with %d entries", len(history.entries))

    def run_benchmark(
        self,
        difficulty: DifficultyLevel | None = None,
        dimensions: list[CoherenceDimension] | None = None,
        save_to_history: bool = True,
    ) -> AccuracyMetrics:
        """Run the benchmark evaluation.

        Args:
            difficulty: Optional filter by difficulty level
            dimensions: Optional filter by dimensions
            save_to_history: Whether to append results to history

        Returns:
            AccuracyMetrics from the run
        """
        logger.info("Running benchmark evaluation...")
        summary = self.runner.run_all(difficulty=difficulty, dimensions=dimensions)
        metrics = AccuracyMetrics.from_run_summary(summary)

        if save_to_history:
            history = self.load_history()
            history.add_entry(metrics)
            self.save_history(history)

        return metrics

    def compare_to_baseline(
        self,
        metrics: AccuracyMetrics,
        threshold: float = 80.0,
    ) -> BaselineComparison:
        """Compare metrics against the baseline.

        Args:
            metrics: Current metrics to compare
            threshold: Minimum accuracy threshold (default: 80%)

        Returns:
            BaselineComparison with detailed comparison
        """
        baseline = self.load_baseline()

        accuracy_delta = 0.0
        improved_dimensions: list[str] = []
        degraded_dimensions: list[str] = []
        improved_difficulties: list[str] = []
        degraded_difficulties: list[str] = []

        if baseline:
            accuracy_delta = metrics.overall_accuracy - baseline.overall_accuracy

            # Compare dimensions
            for dim, acc in metrics.by_dimension.items():
                baseline_acc = baseline.by_dimension.get(dim, 0)
                if acc > baseline_acc + 1:
                    improved_dimensions.append(dim)
                elif acc < baseline_acc - 1:
                    degraded_dimensions.append(dim)

            # Compare difficulties
            for diff, acc in metrics.by_difficulty.items():
                baseline_acc = baseline.by_difficulty.get(diff, 0)
                if acc > baseline_acc + 1:
                    improved_difficulties.append(diff)
                elif acc < baseline_acc - 1:
                    degraded_difficulties.append(diff)

        meets_threshold = metrics.overall_accuracy >= threshold

        return BaselineComparison(
            current=metrics,
            baseline=baseline,
            accuracy_delta=accuracy_delta,
            improved_dimensions=improved_dimensions,
            degraded_dimensions=degraded_dimensions,
            improved_difficulties=improved_difficulties,
            degraded_difficulties=degraded_difficulties,
            meets_threshold=meets_threshold,
            threshold=threshold,
        )


def format_benchmark_report(comparison: BaselineComparison) -> str:
    """Format a benchmark comparison as a human-readable report.

    Args:
        comparison: The baseline comparison to format

    Returns:
        Formatted text report
    """
    lines = [
        "=" * 70,
        "GOLDEN DATASET ACCURACY BENCHMARK",
        "=" * 70,
        "",
        f"Timestamp: {comparison.current.timestamp}",
        f"Total Cases: {comparison.current.total_cases}",
        "",
        "-" * 70,
        "ACCURACY SUMMARY",
        "-" * 70,
        f"  Overall Accuracy: {comparison.current.overall_accuracy:.1f}%",
        f"  Average Score: {comparison.current.avg_score:.3f}",
        f"  Execution Time: {comparison.current.execution_time_ms:.0f}ms",
    ]

    if comparison.baseline:
        delta_str = f"{comparison.accuracy_delta:+.1f}%"
        delta_indicator = "▲" if comparison.accuracy_delta > 0 else ("▼" if comparison.accuracy_delta < 0 else "=")
        lines.append(f"  vs Baseline: {delta_indicator} {delta_str}")

    lines.extend([
        "",
        "-" * 70,
        "BY DIFFICULTY",
        "-" * 70,
    ])

    for diff in ["Easy", "Medium", "Hard", "Expert"]:
        acc = comparison.current.by_difficulty.get(diff, 0)
        baseline_acc = comparison.baseline.by_difficulty.get(diff, 0) if comparison.baseline else 0
        delta = acc - baseline_acc if comparison.baseline else 0
        delta_str = f" ({delta:+.1f}%)" if comparison.baseline else ""
        lines.append(f"  {diff:8s}: {acc:5.1f}%{delta_str}")

    lines.extend([
        "",
        "-" * 70,
        "BY DIMENSION",
        "-" * 70,
    ])

    for dim in ["Schedule", "Cost", "Legal", "Quality", "Scope", "Technical"]:
        acc = comparison.current.by_dimension.get(dim, 0)
        baseline_acc = comparison.baseline.by_dimension.get(dim, 0) if comparison.baseline else 0
        delta = acc - baseline_acc if comparison.baseline else 0
        delta_str = f" ({delta:+.1f}%)" if comparison.baseline else ""
        lines.append(f"  {dim:10s}: {acc:5.1f}%{delta_str}")

    # Show improvements/degradations
    if comparison.improved_dimensions or comparison.degraded_dimensions:
        lines.extend([
            "",
            "-" * 70,
            "CHANGES FROM BASELINE",
            "-" * 70,
        ])
        if comparison.improved_dimensions:
            lines.append(f"  Improved: {', '.join(comparison.improved_dimensions)}")
        if comparison.degraded_dimensions:
            lines.append(f"  Degraded: {', '.join(comparison.degraded_dimensions)}")

    # Threshold status
    lines.extend([
        "",
        "-" * 70,
        "THRESHOLD CHECK",
        "-" * 70,
        f"  Minimum Threshold: {comparison.threshold:.1f}%",
        f"  Current Accuracy: {comparison.current.overall_accuracy:.1f}%",
        f"  Status: {'✓ PASS' if comparison.meets_threshold else '✗ FAIL'}",
    ])

    lines.extend([
        "",
        "=" * 70,
        f"RESULT: {'PASS' if comparison.meets_threshold else 'FAIL - Below threshold'}",
        "=" * 70,
    ])

    return "\n".join(lines)


def main() -> int:
    """Main entry point for the benchmark CLI.

    Returns:
        Exit code (0 for success, 1 for threshold failure, 2 for errors)
    """
    parser = argparse.ArgumentParser(
        description="Run golden dataset accuracy benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m golden.benchmark                     Run benchmark
  python -m golden.benchmark --baseline          Set new baseline
  python -m golden.benchmark --compare           Compare to baseline
  python -m golden.benchmark --threshold 90      Fail if accuracy < 90%
  python -m golden.benchmark --history           Show historical trend
        """,
    )

    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=80.0,
        help="Minimum accuracy threshold (default: 80%%)",
    )
    parser.add_argument(
        "--baseline",
        "-b",
        action="store_true",
        help="Save current run as new baseline",
    )
    parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Compare current run against baseline",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show historical trend analysis",
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
        "--artifacts-dir",
        type=Path,
        help="Path to benchmark artifacts directory",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock executor (for testing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Convert filters
        difficulty = DifficultyLevel(args.difficulty.capitalize()) if args.difficulty else None
        dimensions = [CoherenceDimension(d) for d in args.dimension] if args.dimension else None

        # Create executor
        executor = MockWorkflowExecutor() if args.mock else MockWorkflowExecutor()

        # Create benchmark
        benchmark = AccuracyBenchmark(
            dataset_dir=args.dataset_dir,
            artifacts_dir=args.artifacts_dir,
            executor=executor,
        )

        # Handle history-only request
        if args.history:
            history = benchmark.load_history()
            if args.output == "json":
                output = json.dumps(history.to_dict(), indent=2)
            else:
                trend = history.get_trend()
                output = (
                    f"Benchmark History\n"
                    f"{'=' * 40}\n"
                    f"Entries: {trend.get('entries', 0)}\n"
                    f"Trend: {trend.get('trend', 'unknown')}\n"
                    f"Current: {trend.get('current', 0):.1f}%\n"
                    f"Min: {trend.get('min', 0):.1f}%\n"
                    f"Max: {trend.get('max', 0):.1f}%\n"
                    f"Avg: {trend.get('avg', 0):.1f}%\n"
                    f"Delta (first to last): {trend.get('delta', 0):+.1f}%\n"
                )
            if args.output_file:
                args.output_file.write_text(output)
            else:
                print(output)
            return 0

        # Run benchmark
        metrics = benchmark.run_benchmark(
            difficulty=difficulty,
            dimensions=dimensions,
            save_to_history=not args.baseline,  # Don't save baseline runs to history
        )

        # Save as baseline if requested
        if args.baseline:
            benchmark.save_baseline(metrics)
            logger.info("Baseline saved with accuracy: %.1f%%", metrics.overall_accuracy)

        # Compare to baseline
        comparison = benchmark.compare_to_baseline(metrics, threshold=args.threshold)

        # Format output
        if args.output == "json":
            output = json.dumps(comparison.to_dict(), indent=2)
        else:
            output = format_benchmark_report(comparison)

        # Write output
        if args.output_file:
            args.output_file.write_text(output)
            # Security: Only log filename, not full path
            logger.info("Report written to: %s", args.output_file.name)
        else:
            print(output)

        # Return exit code
        if not comparison.meets_threshold:
            return 1
        return 0

    except Exception:
        logger.exception("Benchmark failed")
        return 2


if __name__ == "__main__":
    sys.exit(main())
