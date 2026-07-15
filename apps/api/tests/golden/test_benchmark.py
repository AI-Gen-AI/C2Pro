"""Tests for golden dataset benchmark runner."""

import json
from pathlib import Path

import pytest

from golden.benchmark import (
    AccuracyBenchmark,
    AccuracyMetrics,
    BaselineComparison,
    BenchmarkHistory,
    format_benchmark_report,
)
from golden.runner import RunSummary


class TestAccuracyMetrics:
    """Tests for AccuracyMetrics dataclass."""

    def test_to_dict(self) -> None:
        """Test metrics serialization to dictionary."""
        metrics = AccuracyMetrics(
            overall_accuracy=85.5,
            by_difficulty={"Easy": 100.0, "Medium": 80.0},
            by_dimension={"Schedule": 90.0, "Cost": 80.0},
            total_cases=25,
            passed_cases=21,
            failed_cases=4,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
            execution_time_ms=1500.0,
        )

        result = metrics.to_dict()

        assert result["overall_accuracy"] == 85.5
        assert result["by_difficulty"]["Easy"] == 100.0
        assert result["by_dimension"]["Schedule"] == 90.0
        assert result["total_cases"] == 25
        assert result["passed_cases"] == 21

    def test_from_run_summary(self) -> None:
        """Test creating metrics from RegressionRunner summary."""
        summary = RunSummary(
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            error_cases=0,
            overall_pass_rate=80.0,
            avg_score=0.8,
            total_time_ms=1000.0,
            by_difficulty={"Easy": {"total": 5, "passed": 5, "failed": 0}},
            by_dimension={"Schedule": {"total": 3, "passed": 2, "failed": 1}},
            timestamp="2026-03-24T12:00:00Z",
            case_results=[],
        )

        metrics = AccuracyMetrics.from_run_summary(summary)

        assert metrics.overall_accuracy == 80.0
        assert metrics.total_cases == 10
        assert metrics.passed_cases == 8
        assert metrics.by_difficulty["Easy"] == 100.0  # 5/5
        assert metrics.by_dimension["Schedule"] == pytest.approx(66.67, rel=0.01)  # 2/3


class TestBenchmarkHistory:
    """Tests for BenchmarkHistory."""

    def test_add_entry(self) -> None:
        """Test adding entries to history."""
        history = BenchmarkHistory()
        metrics = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
        )

        history.add_entry(metrics)

        assert len(history.entries) == 1
        assert history.entries[0].overall_accuracy == 85.0

    def test_max_entries_trimming(self) -> None:
        """Test that history trims old entries when max reached."""
        history = BenchmarkHistory(max_entries=5)

        for i in range(10):
            metrics = AccuracyMetrics(
                overall_accuracy=float(i * 10),
                by_difficulty={},
                by_dimension={},
                total_cases=10,
                passed_cases=i,
                failed_cases=10 - i,
                avg_score=i / 10,
                timestamp=f"2026-03-{i + 1:02d}T12:00:00Z",
            )
            history.add_entry(metrics)

        assert len(history.entries) == 5
        # Should keep the most recent entries (i=5 to i=9)
        assert history.entries[0].overall_accuracy == 50.0
        assert history.entries[-1].overall_accuracy == 90.0

    def test_get_trend_no_data(self) -> None:
        """Test trend analysis with no data."""
        history = BenchmarkHistory()
        trend = history.get_trend()

        assert trend["trend"] == "no_data"
        assert trend["entries"] == 0

    def test_get_trend_insufficient_data(self) -> None:
        """Test trend analysis with single entry."""
        history = BenchmarkHistory()
        metrics = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
        )
        history.add_entry(metrics)

        trend = history.get_trend()

        assert trend["trend"] == "insufficient_data"
        assert trend["entries"] == 1
        assert trend["current"] == 85.0

    def test_get_trend_improving(self) -> None:
        """Test trend detection for improving accuracy."""
        history = BenchmarkHistory()
        # Add entries with improving accuracy
        for i in range(10):
            metrics = AccuracyMetrics(
                overall_accuracy=70.0 + i * 3,  # 70, 73, 76, ..., 97
                by_difficulty={},
                by_dimension={},
                total_cases=10,
                passed_cases=7 + i // 3,
                failed_cases=3 - i // 3,
                avg_score=0.7 + i * 0.03,
                timestamp=f"2026-03-{i + 1:02d}T12:00:00Z",
            )
            history.add_entry(metrics)

        trend = history.get_trend()

        assert trend["trend"] == "improving"
        assert trend["entries"] == 10

    def test_get_trend_stable(self) -> None:
        """Test trend detection for stable accuracy."""
        history = BenchmarkHistory()
        # Add entries with stable accuracy (±1%)
        for i in range(10):
            metrics = AccuracyMetrics(
                overall_accuracy=85.0 + (i % 2) * 0.5,  # 85.0, 85.5, 85.0, ...
                by_difficulty={},
                by_dimension={},
                total_cases=10,
                passed_cases=8,
                failed_cases=2,
                avg_score=0.85,
                timestamp=f"2026-03-{i + 1:02d}T12:00:00Z",
            )
            history.add_entry(metrics)

        trend = history.get_trend()

        assert trend["trend"] == "stable"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "entries": [
                {
                    "overall_accuracy": 85.0,
                    "by_difficulty": {"Easy": 100.0},
                    "by_dimension": {"Schedule": 80.0},
                    "total_cases": 10,
                    "passed_cases": 8,
                    "failed_cases": 2,
                    "avg_score": 0.85,
                    "timestamp": "2026-03-24T12:00:00Z",
                    "execution_time_ms": 1000.0,
                }
            ],
            "max_entries": 100,
        }

        history = BenchmarkHistory.from_dict(data)

        assert len(history.entries) == 1
        assert history.entries[0].overall_accuracy == 85.0
        assert history.max_entries == 100


class TestBaselineComparison:
    """Tests for BaselineComparison."""

    def test_to_dict(self) -> None:
        """Test comparison serialization."""
        current = AccuracyMetrics(
            overall_accuracy=90.0,
            by_difficulty={"Easy": 100.0},
            by_dimension={"Schedule": 95.0},
            total_cases=10,
            passed_cases=9,
            failed_cases=1,
            avg_score=0.9,
            timestamp="2026-03-24T12:00:00Z",
        )
        baseline = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={"Easy": 100.0},
            by_dimension={"Schedule": 80.0},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-23T12:00:00Z",
        )

        comparison = BaselineComparison(
            current=current,
            baseline=baseline,
            accuracy_delta=5.0,
            improved_dimensions=["Schedule"],
            degraded_dimensions=[],
            improved_difficulties=[],
            degraded_difficulties=[],
            meets_threshold=True,
            threshold=80.0,
        )

        result = comparison.to_dict()

        assert result["accuracy_delta"] == 5.0
        assert result["improved_dimensions"] == ["Schedule"]
        assert result["meets_threshold"] is True
        assert result["current"]["overall_accuracy"] == 90.0
        assert result["baseline"]["overall_accuracy"] == 85.0


class TestAccuracyBenchmark:
    """Tests for AccuracyBenchmark runner."""

    @pytest.fixture
    def temp_dataset_dir(self, tmp_path: Path) -> Path:
        """Create a temporary dataset directory with cases."""
        cases_dir = tmp_path / "cases" / "easy"
        cases_dir.mkdir(parents=True)

        # Create a minimal valid case
        case = {
            "case_id": "SCHED-001",
            "name": "Test schedule case",
            "dimensions": ["Schedule"],
            "difficulty": "Easy",
            "input_documents": {
                "contract_path": "/test/contract.pdf",
                "schedule_path": "/test/schedule.pdf",
            },
            "trajectory": {"required_nodes": ["analyze", "report"]},
            "expected_issues": [
                {
                    "rule_id": "SCHED-001",
                    "dimension": "Schedule",
                    "severity": "high",
                }
            ],
        }
        (cases_dir / "SCHED-001.json").write_text(json.dumps(case))

        return tmp_path

    def test_run_benchmark(self, temp_dataset_dir: Path) -> None:
        """Test running a benchmark."""
        benchmark = AccuracyBenchmark(temp_dataset_dir)

        metrics = benchmark.run_benchmark(save_to_history=False)

        assert metrics.total_cases == 1
        assert metrics.overall_accuracy >= 0

    def test_save_and_load_baseline(self, temp_dataset_dir: Path) -> None:
        """Test saving and loading baseline."""
        benchmark = AccuracyBenchmark(temp_dataset_dir)
        metrics = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={"Easy": 100.0},
            by_dimension={"Schedule": 85.0},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
        )

        benchmark.save_baseline(metrics)
        loaded = benchmark.load_baseline()

        assert loaded is not None
        assert loaded.overall_accuracy == 85.0
        assert loaded.by_difficulty["Easy"] == 100.0

    def test_save_and_load_history(self, temp_dataset_dir: Path) -> None:
        """Test saving and loading history."""
        benchmark = AccuracyBenchmark(temp_dataset_dir)
        history = BenchmarkHistory()
        metrics = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
        )
        history.add_entry(metrics)

        benchmark.save_history(history)
        loaded = benchmark.load_history()

        assert len(loaded.entries) == 1
        assert loaded.entries[0].overall_accuracy == 85.0

    def test_compare_to_baseline(self, temp_dataset_dir: Path) -> None:
        """Test baseline comparison."""
        benchmark = AccuracyBenchmark(temp_dataset_dir)

        # Save a baseline
        baseline = AccuracyMetrics(
            overall_accuracy=80.0,
            by_difficulty={"Easy": 80.0, "Medium": 75.0},
            by_dimension={"Schedule": 70.0, "Cost": 80.0},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.8,
            timestamp="2026-03-23T12:00:00Z",
        )
        benchmark.save_baseline(baseline)

        # Compare current metrics
        current = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={"Easy": 90.0, "Medium": 70.0},
            by_dimension={"Schedule": 85.0, "Cost": 75.0},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
        )

        comparison = benchmark.compare_to_baseline(current, threshold=80.0)

        assert comparison.accuracy_delta == 5.0
        assert "Schedule" in comparison.improved_dimensions  # 70 -> 85
        assert "Easy" in comparison.improved_difficulties  # 80 -> 90
        assert "Medium" in comparison.degraded_difficulties  # 75 -> 70
        assert comparison.meets_threshold is True

    def test_compare_without_baseline(self, temp_dataset_dir: Path) -> None:
        """Test comparison when no baseline exists."""
        benchmark = AccuracyBenchmark(temp_dataset_dir)
        current = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
        )

        comparison = benchmark.compare_to_baseline(current, threshold=80.0)

        assert comparison.baseline is None
        assert comparison.accuracy_delta == 0.0
        assert comparison.meets_threshold is True

    def test_threshold_failure(self, temp_dataset_dir: Path) -> None:
        """Test threshold check failure."""
        benchmark = AccuracyBenchmark(temp_dataset_dir)
        current = AccuracyMetrics(
            overall_accuracy=75.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=7,
            failed_cases=3,
            avg_score=0.75,
            timestamp="2026-03-24T12:00:00Z",
        )

        comparison = benchmark.compare_to_baseline(current, threshold=80.0)

        assert comparison.meets_threshold is False


class TestFormatBenchmarkReport:
    """Tests for benchmark report formatting."""

    def test_format_report_basic(self) -> None:
        """Test basic report formatting."""
        current = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={"Easy": 100.0, "Medium": 80.0},
            by_dimension={"Schedule": 90.0, "Cost": 80.0},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-24T12:00:00Z",
            execution_time_ms=1500.0,
        )

        comparison = BaselineComparison(
            current=current,
            baseline=None,
            accuracy_delta=0.0,
            improved_dimensions=[],
            degraded_dimensions=[],
            improved_difficulties=[],
            degraded_difficulties=[],
            meets_threshold=True,
            threshold=80.0,
        )

        report = format_benchmark_report(comparison)

        assert "GOLDEN DATASET ACCURACY BENCHMARK" in report
        assert "Overall Accuracy: 85.0%" in report
        assert "Status: ✓ PASS" in report

    def test_format_report_with_baseline(self) -> None:
        """Test report formatting with baseline comparison."""
        current = AccuracyMetrics(
            overall_accuracy=90.0,
            by_difficulty={"Easy": 100.0},
            by_dimension={"Schedule": 95.0},
            total_cases=10,
            passed_cases=9,
            failed_cases=1,
            avg_score=0.9,
            timestamp="2026-03-24T12:00:00Z",
        )
        baseline = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={"Easy": 95.0},
            by_dimension={"Schedule": 80.0},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-03-23T12:00:00Z",
        )

        comparison = BaselineComparison(
            current=current,
            baseline=baseline,
            accuracy_delta=5.0,
            improved_dimensions=["Schedule"],
            degraded_dimensions=[],
            improved_difficulties=["Easy"],
            degraded_difficulties=[],
            meets_threshold=True,
            threshold=80.0,
        )

        report = format_benchmark_report(comparison)

        assert "vs Baseline:" in report
        assert "+5.0%" in report
        assert "Improved: Schedule" in report

    def test_format_report_threshold_failure(self) -> None:
        """Test report formatting when below threshold."""
        current = AccuracyMetrics(
            overall_accuracy=70.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=7,
            failed_cases=3,
            avg_score=0.7,
            timestamp="2026-03-24T12:00:00Z",
        )

        comparison = BaselineComparison(
            current=current,
            baseline=None,
            accuracy_delta=0.0,
            improved_dimensions=[],
            degraded_dimensions=[],
            improved_difficulties=[],
            degraded_difficulties=[],
            meets_threshold=False,
            threshold=80.0,
        )

        report = format_benchmark_report(comparison)

        assert "Status: ✗ FAIL" in report
        assert "FAIL - Below threshold" in report
