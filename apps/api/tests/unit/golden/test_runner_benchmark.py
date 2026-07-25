"""TS-UD-GOLD-RUN-001: Unit tests for golden runner, benchmark, and loader."""
from __future__ import annotations

import json
from pathlib import Path

from golden.benchmark import (
    AccuracyBenchmark,
    AccuracyMetrics,
    BaselineComparison,
    BenchmarkHistory,
    format_benchmark_report,
)
from golden.loader import GoldenDatasetLoader
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


def _make_case(
    case_id: str = "SCHED-001",
    difficulty: DifficultyLevel = DifficultyLevel.Easy,
    dims: list[CoherenceDimension] | None = None,
) -> GoldenCase:
    return GoldenCase(
        case_id=case_id,
        name=f"Test case {case_id}",
        dimensions=dims or [CoherenceDimension.Schedule],
        difficulty=difficulty,
        input_documents=InputDocuments(
            contract_path="contract.pdf",
            schedule_path="schedule.pdf",
        ),
        trajectory=TrajectoryConstraint(required_nodes=["node_a"]),
    )


class TestWorkflowResult:
    def test_defaults(self) -> None:
        r = WorkflowResult()
        assert r.nodes_visited == []
        assert r.tool_calls == []
        assert r.final_state == {}
        assert r.error is None
        assert r.execution_time_ms == 0.0


class TestMockWorkflowExecutor:
    def test_execute_returns_nodes(self) -> None:
        case = _make_case()
        executor = MockWorkflowExecutor()
        result = executor.execute(case)
        assert "node_a" in result.nodes_visited
        assert result.error is None

    def test_execute_with_tool_calls(self) -> None:
        from golden.schemas import ToolCallAssertion

        case = _make_case()
        case = case.model_copy(
            update={
                "tool_calls": [
                    ToolCallAssertion(
                        tool_name="search", required_args=["query"], min_calls=1
                    )
                ]
            }
        )
        executor = MockWorkflowExecutor()
        result = executor.execute(case)
        assert any(tc.tool_name == "search" for tc in result.tool_calls)


class TestCaseResult:
    def test_to_dict(self) -> None:
        cr = CaseResult(case_id="X-001", passed=True, overall_score=0.95)
        d = cr.to_dict()
        assert d["case_id"] == "X-001"
        assert d["passed"] is True
        assert d["overall_score"] == 0.95


class TestRunSummary:
    def test_to_dict(self) -> None:
        s = RunSummary(
            total_cases=5,
            passed_cases=4,
            failed_cases=1,
            error_cases=0,
            overall_pass_rate=80.0,
            avg_score=0.85,
            total_time_ms=123.45,
            by_difficulty={"Easy": {"total": 5, "passed": 4, "failed": 1}},
            by_dimension={"Schedule": {"total": 5, "passed": 4, "failed": 1}},
            timestamp="2026-01-01T00:00:00",
        )
        d = s.to_dict()
        assert d["summary"]["total_cases"] == 5
        assert d["summary"]["overall_pass_rate"] == 80.0


class TestFormatTextReport:
    def test_contains_header(self) -> None:
        s = RunSummary(
            total_cases=1,
            passed_cases=1,
            failed_cases=0,
            error_cases=0,
            overall_pass_rate=100.0,
            avg_score=1.0,
            total_time_ms=10.0,
            by_difficulty={"Easy": {"total": 1, "passed": 1, "failed": 0}},
            by_dimension={"Schedule": {"total": 1, "passed": 1, "failed": 0}},
            timestamp="2026-01-01T00:00:00",
        )
        report = format_text_report(s)
        assert "GOLDEN DATASET REGRESSION TEST REPORT" in report
        assert "RESULT: PASS" in report

    def test_fail_report(self) -> None:
        s = RunSummary(
            total_cases=1,
            passed_cases=0,
            failed_cases=1,
            error_cases=0,
            overall_pass_rate=0.0,
            avg_score=0.0,
            total_time_ms=10.0,
            by_difficulty={},
            by_dimension={},
            timestamp="2026-01-01T00:00:00",
        )
        report = format_text_report(s)
        assert "RESULT: FAIL" in report


class TestRegressionRunner:
    def test_run_case_with_mock(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        case = _make_case()
        case_file = cases_dir / "SCHED-001.json"
        case_file.write_text(json.dumps(case.model_dump(mode="json")))

        runner = RegressionRunner(tmp_path, MockWorkflowExecutor())
        result = runner.run_case(case)
        assert result.passed is True
        assert result.overall_score > 0

    def test_run_case_with_error(self) -> None:
        from golden.runner import WorkflowExecutor

        class _FailingExecutor(WorkflowExecutor):
            def execute(self, case: GoldenCase) -> WorkflowResult:
                return WorkflowResult(error="boom")

        runner = RegressionRunner("/tmp/nonexistent", _FailingExecutor())
        result = runner.run_case(_make_case())
        assert result.passed is False
        assert result.error == "boom"


class TestAccuracyMetrics:
    def test_from_run_summary(self) -> None:
        s = RunSummary(
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            error_cases=0,
            overall_pass_rate=80.0,
            avg_score=0.85,
            total_time_ms=100.0,
            by_difficulty={"Easy": {"total": 5, "passed": 5, "failed": 0}},
            by_dimension={"Schedule": {"total": 10, "passed": 8, "failed": 2}},
            timestamp="2026-01-01T00:00:00",
        )
        m = AccuracyMetrics.from_run_summary(s)
        assert m.overall_accuracy == 80.0
        assert m.by_difficulty["Easy"] == 100.0
        assert m.by_dimension["Schedule"] == 80.0

    def test_to_dict(self) -> None:
        m = AccuracyMetrics(
            overall_accuracy=90.0,
            by_difficulty={},
            by_dimension={},
            total_cases=5,
            passed_cases=5,
            failed_cases=0,
            avg_score=0.95,
            timestamp="2026-01-01",
        )
        d = m.to_dict()
        assert d["overall_accuracy"] == 90.0


class TestBenchmarkHistory:
    def test_add_and_trim(self) -> None:
        h = BenchmarkHistory(max_entries=3)
        for i in range(5):
            h.add_entry(
                AccuracyMetrics(
                    overall_accuracy=float(i),
                    by_difficulty={},
                    by_dimension={},
                    total_cases=1,
                    passed_cases=1,
                    failed_cases=0,
                    avg_score=1.0,
                    timestamp=f"2026-01-0{i+1}",
                )
            )
        assert len(h.entries) == 3
        assert h.entries[-1].overall_accuracy == 4.0

    def test_get_trend_no_data(self) -> None:
        h = BenchmarkHistory()
        t = h.get_trend()
        assert t["trend"] == "no_data"

    def test_get_trend_improving(self) -> None:
        h = BenchmarkHistory()
        for acc in [50.0, 55.0, 60.0, 70.0]:
            h.add_entry(
                AccuracyMetrics(
                    overall_accuracy=acc,
                    by_difficulty={},
                    by_dimension={},
                    total_cases=1,
                    passed_cases=1,
                    failed_cases=0,
                    avg_score=1.0,
                    timestamp="2026-01-01",
                )
            )
        t = h.get_trend()
        assert t["trend"] == "improving"

    def test_get_trend_stable(self) -> None:
        h = BenchmarkHistory()
        for _ in range(4):
            h.add_entry(
                AccuracyMetrics(
                    overall_accuracy=80.0,
                    by_difficulty={},
                    by_dimension={},
                    total_cases=1,
                    passed_cases=1,
                    failed_cases=0,
                    avg_score=1.0,
                    timestamp="2026-01-01",
                )
            )
        t = h.get_trend()
        assert t["trend"] == "stable"

    def test_from_dict(self) -> None:
        data = {
            "entries": [
                {
                    "overall_accuracy": 80.0,
                    "by_difficulty": {},
                    "by_dimension": {},
                    "total_cases": 1,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "avg_score": 1.0,
                    "timestamp": "2026-01-01",
                }
            ],
            "max_entries": 100,
        }
        h = BenchmarkHistory.from_dict(data)
        assert len(h.entries) == 1


class TestAccuracyBenchmark:
    def test_compare_to_baseline_no_baseline(self, tmp_path: Path) -> None:
        benchmark = AccuracyBenchmark(tmp_path, tmp_path / ".bench")
        m = AccuracyMetrics(
            overall_accuracy=85.0,
            by_difficulty={},
            by_dimension={},
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            avg_score=0.85,
            timestamp="2026-01-01",
        )
        c = benchmark.compare_to_baseline(m, threshold=80.0)
        assert c.meets_threshold is True
        assert c.baseline is None

    def test_save_and_load_baseline(self, tmp_path: Path) -> None:
        benchmark = AccuracyBenchmark(tmp_path, tmp_path / ".bench")
        m = AccuracyMetrics(
            overall_accuracy=90.0,
            by_difficulty={"Easy": 100.0},
            by_dimension={"Schedule": 90.0},
            total_cases=5,
            passed_cases=5,
            failed_cases=0,
            avg_score=0.95,
            timestamp="2026-01-01",
        )
        benchmark.save_baseline(m)
        loaded = benchmark.load_baseline()
        assert loaded is not None
        assert loaded.overall_accuracy == 90.0

    def test_load_baseline_no_file(self, tmp_path: Path) -> None:
        benchmark = AccuracyBenchmark(tmp_path, tmp_path / ".bench")
        assert benchmark.load_baseline() is None


class TestFormatBenchmarkReport:
    def test_contains_threshold(self) -> None:
        c = BaselineComparison(
            current=AccuracyMetrics(
                overall_accuracy=85.0,
                by_difficulty={},
                by_dimension={},
                total_cases=10,
                passed_cases=8,
                failed_cases=2,
                avg_score=0.85,
                timestamp="2026-01-01",
            ),
            baseline=None,
            accuracy_delta=0.0,
            improved_dimensions=[],
            degraded_dimensions=[],
            improved_difficulties=[],
            degraded_difficulties=[],
            meets_threshold=True,
            threshold=80.0,
        )
        report = format_benchmark_report(c)
        assert "THRESHOLD CHECK" in report
        assert "PASS" in report


class TestGoldenDatasetLoader:
    def test_load_case(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        case = _make_case()
        (cases_dir / "SCHED-001.json").write_text(
            json.dumps(case.model_dump(mode="json"))
        )
        loader = GoldenDatasetLoader(tmp_path)
        loaded = loader.load_case("SCHED-001")
        assert loaded is not None
        assert loaded.case_id == "SCHED-001"

    def test_load_case_not_found(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        loader = GoldenDatasetLoader(tmp_path)
        assert loader.load_case("NOPE-001") is None

    def test_load_case_rejects_path_traversal(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        loader = GoldenDatasetLoader(tmp_path)
        assert loader.load_case("../../etc/passwd") is None

    def test_load_all_cases(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        for cid, dim in [
            ("SCHED-001", CoherenceDimension.Schedule),
            ("SCHED-002", CoherenceDimension.Schedule),
        ]:
            case = _make_case(case_id=cid, dims=[dim])
            (cases_dir / f"{cid}.json").write_text(
                json.dumps(case.model_dump(mode="json"))
            )
        loader = GoldenDatasetLoader(tmp_path)
        all_cases = loader.load_all_cases()
        assert len(all_cases) == 2

    def test_filter_by_difficulty(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        easy = _make_case("SCHED-001", DifficultyLevel.Easy)
        hard = _make_case("SCHED-002", DifficultyLevel.Hard)
        (cases_dir / "SCHED-001.json").write_text(
            json.dumps(easy.model_dump(mode="json"))
        )
        (cases_dir / "SCHED-002.json").write_text(
            json.dumps(hard.model_dump(mode="json"))
        )
        loader = GoldenDatasetLoader(tmp_path)
        easy_cases = loader.filter_by_difficulty(DifficultyLevel.Easy)
        assert len(easy_cases) == 1
        assert easy_cases[0].difficulty == DifficultyLevel.Easy

    def test_hierarchical_structure(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases" / "easy"
        cases_dir.mkdir(parents=True)
        case = _make_case()
        (cases_dir / "SCHED-001.json").write_text(
            json.dumps(case.model_dump(mode="json"))
        )
        loader = GoldenDatasetLoader(tmp_path)
        loaded = loader.load_case("SCHED-001")
        assert loaded is not None

    def test_get_statistics(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        case = _make_case()
        (cases_dir / "SCHED-001.json").write_text(
            json.dumps(case.model_dump(mode="json"))
        )
        loader = GoldenDatasetLoader(tmp_path)
        stats = loader.get_statistics()
        assert stats["total_cases"] == 1

    def test_get_statistics_empty(self, tmp_path: Path) -> None:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        loader = GoldenDatasetLoader(tmp_path)
        stats = loader.get_statistics()
        assert stats["total_cases"] == 0
