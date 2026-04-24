"""TS-INF-PERF-056-001

Run release-oriented performance smoke benchmarks and format evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BenchmarkResult = Literal["pass", "fail"]


@dataclass(frozen=True)
class PercentileResult:
    p50_ms: float
    p95_ms: float
    p99_ms: float


@dataclass(frozen=True)
class PerformanceTarget:
    key: str
    layer: str
    metric: str
    target_ms: float
    description: str
    path: str = ""
    method: str = "GET"


@dataclass(frozen=True)
class BenchmarkMeasurement:
    target: PerformanceTarget
    sample_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    result: BenchmarkResult


@dataclass(frozen=True)
class BenchmarkReport:
    result: BenchmarkResult
    run_id: str
    environment: str
    tooling: str
    measurements: list[BenchmarkMeasurement]


DEFAULT_TARGETS: tuple[PerformanceTarget, ...] = (
    PerformanceTarget(
        key="api_health",
        layer="API",
        metric="Health P95",
        target_ms=100.0,
        description="Health endpoint P95",
        path="/health",
    ),
    PerformanceTarget(
        key="api_list",
        layer="API",
        metric="List P95",
        target_ms=500.0,
        description="Authenticated list endpoint P95",
        path="/api/v1/projects",
    ),
    PerformanceTarget(
        key="worker_acceptance",
        layer="Worker",
        metric="Queue acceptance",
        target_ms=1500.0,
        description="Initial async job acceptance response",
        path="/api/v1/health/worker",
    ),
)


def calculate_percentiles(samples_ms: list[float]) -> PercentileResult:
    if not samples_ms:
        raise ValueError("at least one latency sample is required")

    sorted_samples = sorted(samples_ms)

    def nearest_rank(percentile: float) -> float:
        rank = math.ceil((percentile / 100.0) * len(sorted_samples))
        return sorted_samples[max(rank - 1, 0)]

    return PercentileResult(
        p50_ms=nearest_rank(50.0),
        p95_ms=nearest_rank(95.0),
        p99_ms=nearest_rank(99.0),
    )


def evaluate_measurements(
    *,
    targets: list[PerformanceTarget],
    samples_by_target: dict[str, list[float]],
    environment: str,
    run_id: str,
    tooling: str,
) -> BenchmarkReport:
    measurements: list[BenchmarkMeasurement] = []

    for target in targets:
        samples = samples_by_target.get(target.key, [])
        percentiles = calculate_percentiles(samples)
        result: BenchmarkResult = "pass" if percentiles.p95_ms < target.target_ms else "fail"
        measurements.append(
            BenchmarkMeasurement(
                target=target,
                sample_count=len(samples),
                p50_ms=percentiles.p50_ms,
                p95_ms=percentiles.p95_ms,
                p99_ms=percentiles.p99_ms,
                result=result,
            )
        )

    overall: BenchmarkResult = "pass"
    if any(measurement.result == "fail" for measurement in measurements):
        overall = "fail"

    return BenchmarkReport(
        result=overall,
        run_id=run_id,
        environment=environment,
        tooling=tooling,
        measurements=measurements,
    )


def format_markdown_report(report: BenchmarkReport) -> str:
    lines = [
        "# Performance Evidence",
        "",
        "Test Suite ID: `TS-INF-PERF-056-001`",
        "",
        "## Acceptance Targets",
        "",
        "Reference: `docs/performance/baseline.md`",
        "",
        "| Layer | Metric | Target | Measured P95 | Result | Notes |",
        "| ----- | ------ | ------ | ------------ | ------ | ----- |",
    ]

    for measurement in report.measurements:
        result_label = "Pass" if measurement.result == "pass" else "Fail"
        lines.append(
            "| "
            f"{measurement.target.layer} | "
            f"{measurement.target.metric} | "
            f"`< {measurement.target.target_ms:.0f} ms` | "
            f"`{measurement.p95_ms:.2f} ms` | "
            f"{result_label} | "
            f"p50 `{measurement.p50_ms:.2f} ms`, "
            f"p99 `{measurement.p99_ms:.2f} ms`, "
            f"{measurement.sample_count} samples |"
        )

    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Tooling used: `{report.tooling}`",
            f"- Run identifier: `{report.run_id}`",
            f"- Environment: `{report.environment}`",
            f"- Regression assessment: `{report.result}`",
            "",
        ]
    )
    return "\n".join(lines)


def _request_latency_ms(url: str, method: str, timeout_seconds: float, bearer_token: str | None) -> float:
    headers = {"User-Agent": "c2pro-performance-benchmark/1.0"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    request = Request(url=url, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response.read()
    except HTTPError as exc:
        exc.read()
        if exc.code >= 500:
            raise
    except URLError:
        raise
    return (time.perf_counter() - started) * 1000.0


def collect_http_samples(
    *,
    base_url: str,
    targets: list[PerformanceTarget],
    sample_count: int,
    timeout_seconds: float,
    bearer_token: str | None,
) -> dict[str, list[float]]:
    if sample_count < 1:
        raise ValueError("sample_count must be at least 1")

    normalized_base_url = base_url.rstrip("/")
    samples: dict[str, list[float]] = {}
    for target in targets:
        if not target.path:
            continue
        target_samples: list[float] = []
        for _ in range(sample_count):
            target_samples.append(
                _request_latency_ms(
                    url=f"{normalized_base_url}{target.path}",
                    method=target.method,
                    timeout_seconds=timeout_seconds,
                    bearer_token=bearer_token,
                )
            )
        samples[target.key] = target_samples
    return samples


def _load_samples_json(samples_path: Path) -> dict[str, list[float]]:
    payload = json.loads(samples_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("samples JSON must contain an object keyed by target")

    samples: dict[str, list[float]] = {}
    for key, values in payload.items():
        if not isinstance(key, str) or not isinstance(values, list):
            raise ValueError("samples JSON must map target keys to arrays")
        samples[key] = [float(value) for value in values]
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Run C2Pro performance smoke benchmarks")
    parser.add_argument("--base-url", help="Base URL to benchmark, for example http://localhost:8000")
    parser.add_argument("--samples-json", type=Path, help="Evaluate pre-collected latency samples")
    parser.add_argument("--samples", type=int, default=5, help="Number of HTTP samples per target")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--environment", default="local", help="Environment label for evidence")
    parser.add_argument("--run-id", default=f"perf-{int(time.time())}", help="Run identifier")
    parser.add_argument("--bearer-token", help="Optional bearer token for authenticated endpoints")
    parser.add_argument("--output-md", type=Path, help="Optional markdown output path")
    args = parser.parse_args()

    targets = list(DEFAULT_TARGETS)
    if args.samples_json:
        samples_by_target = _load_samples_json(args.samples_json)
        tooling = "pre-collected latency samples"
    elif args.base_url:
        samples_by_target = collect_http_samples(
            base_url=args.base_url,
            targets=targets,
            sample_count=args.samples,
            timeout_seconds=args.timeout,
            bearer_token=args.bearer_token,
        )
        tooling = "urllib smoke benchmark"
    else:
        parser.error("either --base-url or --samples-json is required")

    report = evaluate_measurements(
        targets=targets,
        samples_by_target=samples_by_target,
        environment=args.environment,
        run_id=args.run_id,
        tooling=tooling,
    )
    markdown = format_markdown_report(report)
    if args.output_md:
        args.output_md.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)

    return 0 if report.result == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
