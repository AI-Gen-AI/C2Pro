"""Render C2Pro quality gate reports.

Test Suite ID: TS-QA-CONTRACT-COVERAGE-TRACK-C-001
Backlog: TASK-QA-212, TASK-QA-213
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class GateMetric:
    name: str
    percent: float | None
    detail: str

    @property
    def display_percent(self) -> str:
        if self.percent is None:
            return "n/a"
        return f"{self.percent:.2f}%"


def _read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _number(data: dict[str, object], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int | float):
            return float(value)
    return None


def _contract_metric(path: Path | None) -> GateMetric:
    if path is None or not path.exists():
        return GateMetric("Contract coverage", None, "contract-coverage.json not found")
    data = _read_json(path)
    total = _number(data, "total_operations", "total", "operations_total")
    covered = _number(data, "covered_operations", "covered", "operations_covered")
    percent = _number(data, "coverage_percent", "coverage_pct", "percent")
    if percent is None and total and covered is not None:
        percent = covered / total * 100
    detail = f"{int(covered or 0)}/{int(total or 0)} operations" if total is not None else path.name
    return GateMetric("Contract coverage", percent, detail)


def _wireframe_metric(path: Path | None) -> GateMetric:
    if path is None or not path.exists():
        return GateMetric("Wireframe coverage", None, "wireframe-coverage.json not found")
    data = _read_json(path)
    total = _number(data, "total_wireframes", "total")
    covered = _number(data, "covered", "covered_wireframes")
    percent = _number(data, "coverage_pct", "coverage_percent", "percent")
    if percent is None and total and covered is not None:
        percent = covered / total * 100
    detail = f"{int(covered or 0)}/{int(total or 0)} wireframes" if total is not None else path.name
    return GateMetric("Wireframe coverage", percent, detail)


def _first_existing(paths: Iterable[str]) -> Path | None:
    for raw_path in paths:
        path = Path(raw_path)
        if path.exists():
            return path
    return None


def _expand_paths(paths: Iterable[str], patterns: Iterable[str]) -> list[str]:
    expanded = list(paths)
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        expanded.extend(matches)
    return expanded


def _coverage_metric(paths: Iterable[str]) -> GateMetric:
    path = _first_existing(paths)
    if path is None:
        return GateMetric("Python coverage", None, "coverage.xml not found")
    root = ET.parse(path).getroot()
    line_rate = float(root.attrib.get("line-rate", "0") or 0)
    return GateMetric("Python coverage", line_rate * 100, path.name)


def _junit_metric(paths: Iterable[str]) -> GateMetric:
    total = failures = errors = skipped = 0
    parsed_files = 0
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
        for suite in suites:
            total += int(suite.attrib.get("tests", 0) or 0)
            failures += int(suite.attrib.get("failures", 0) or 0)
            errors += int(suite.attrib.get("errors", 0) or 0)
            skipped += int(suite.attrib.get("skipped", 0) or 0)
        parsed_files += 1
    if total == 0:
        return GateMetric("JUnit results", None, "JUnit XML not found")
    passed = max(total - failures - errors - skipped, 0)
    percent = passed / total * 100
    detail = f"{passed}/{total} passed, {failures} failed, {errors} errors, {skipped} skipped"
    if parsed_files > 1:
        detail = f"{detail} across {parsed_files} files"
    return GateMetric("JUnit results", percent, detail)


def _render_report(metrics: list[GateMetric], contract_delta: float | None) -> str:
    lines = [
        "## C2Pro Quality Gate Report",
        "",
        "| Gate | Result | Detail |",
        "| --- | ---: | --- |",
    ]
    for metric in metrics:
        lines.append(f"| {metric.name} | {metric.display_percent} | {metric.detail} |")
    lines.append("")
    if contract_delta is None:
        lines.append("Contract coverage delta vs base: n/a")
    else:
        lines.append(f"Contract coverage delta vs base: {contract_delta:+.2f}%")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render C2Pro quality gate markdown")
    parser.add_argument("--contract-coverage", type=Path)
    parser.add_argument("--wireframe-coverage", type=Path)
    parser.add_argument("--coverage-xml", action="append", default=[])
    parser.add_argument("--coverage-glob", action="append", default=[])
    parser.add_argument("--junit-xml", action="append", default=[])
    parser.add_argument("--junit-glob", action="append", default=[])
    parser.add_argument("--output", type=Path, default=Path("quality-report.md"))
    parser.add_argument("--base-contract-coverage", type=float)
    parser.add_argument("--max-contract-drop", type=float, default=2.0)
    parser.add_argument("--fail-on-contract-drop", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    coverage_paths = _expand_paths(args.coverage_xml, args.coverage_glob)
    junit_paths = _expand_paths(args.junit_xml, args.junit_glob)
    contract = _contract_metric(args.contract_coverage)
    metrics = [
        contract,
        _wireframe_metric(args.wireframe_coverage),
        _coverage_metric(coverage_paths),
        _junit_metric(junit_paths),
    ]
    contract_delta = None
    if args.base_contract_coverage is not None and contract.percent is not None:
        contract_delta = contract.percent - args.base_contract_coverage

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_render_report(metrics, contract_delta), encoding="utf-8")
    print(f"Quality report written to {args.output}")

    if (
        args.fail_on_contract_drop
        and contract_delta is not None
        and contract_delta < -args.max_contract_drop
    ):
        drop = abs(contract_delta)
        print(
            f"Contract coverage dropped by {drop:.2f}%, exceeding {args.max_contract_drop:.2f}% threshold.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
