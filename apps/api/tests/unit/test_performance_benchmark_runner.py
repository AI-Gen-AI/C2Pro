"""TS-INF-PERF-056-001

Regression tests for the TASK-INF-056 performance benchmark runner.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    module_path = repo_root / "scripts" / "run_performance_benchmarks.py"
    spec = importlib.util.spec_from_file_location("run_performance_benchmarks", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calculates_latency_percentiles_from_sorted_samples() -> None:
    module = _load_module()

    result = module.calculate_percentiles([10.0, 20.0, 30.0, 40.0, 50.0])

    assert result.p50_ms == 30.0
    assert result.p95_ms == 50.0
    assert result.p99_ms == 50.0


def test_evaluates_measurements_against_approved_targets() -> None:
    module = _load_module()
    targets = [
        module.PerformanceTarget(
            key="api_health",
            layer="API",
            metric="Health P95",
            target_ms=100.0,
            description="Health endpoint",
        ),
        module.PerformanceTarget(
            key="api_list",
            layer="API",
            metric="List P95",
            target_ms=500.0,
            description="Authenticated list endpoint",
        ),
    ]
    samples_by_target = {
        "api_health": [20.0, 30.0, 40.0],
        "api_list": [250.0, 500.0, 750.0],
    }

    report = module.evaluate_measurements(
        targets=targets,
        samples_by_target=samples_by_target,
        environment="local",
        run_id="TASK-INF-056-red",
        tooling="synthetic samples",
    )

    assert report.result == "fail"
    assert [row.result for row in report.measurements] == ["pass", "fail"]


def test_formats_release_ready_markdown_evidence() -> None:
    module = _load_module()
    report = module.BenchmarkReport(
        result="pass",
        run_id="TASK-INF-056-green",
        environment="local",
        tooling="urllib smoke benchmark",
        measurements=[
            module.BenchmarkMeasurement(
                target=module.PerformanceTarget(
                    key="api_health",
                    layer="API",
                    metric="Health P95",
                    target_ms=100.0,
                    description="Health endpoint",
                ),
                sample_count=3,
                p50_ms=25.0,
                p95_ms=45.0,
                p99_ms=45.0,
                result="pass",
            )
        ],
    )

    markdown = module.format_markdown_report(report)

    assert "TS-INF-PERF-056-001" in markdown
    assert "| API | Health P95 | `< 100 ms` | `45.00 ms` | Pass |" in markdown
    assert "- Tooling used: `urllib smoke benchmark`" in markdown
    assert "- Run identifier: `TASK-INF-056-green`" in markdown
