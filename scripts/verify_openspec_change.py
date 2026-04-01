"""TS-OPS-OPENSPEC-VERIFY-001

Docs-first verifier for OpenSpec process-only changes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any

import yaml


EXIT_OK = 0
EXIT_NON_COMPLIANT = 1
EXIT_RUNTIME_DRIFT = 2

RFC_2119_PATTERN = re.compile(r"\b(MUST|SHALL|SHOULD|MAY)\b")


@dataclass(frozen=True)
class VerifyInput:
    change_name: str
    repo_root: Path


@dataclass(frozen=True)
class ParsedScenario:
    requirement_name: str
    name: str
    body_lines: tuple[str, ...]
    check_id: str
    spec_path: Path


@dataclass(frozen=True)
class ParsedRequirement:
    name: str
    statement: str
    scenarios: tuple[ParsedScenario, ...]
    spec_path: Path


@dataclass(frozen=True)
class ParsedSpec:
    spec_path: Path
    requirements: tuple[ParsedRequirement, ...]


@dataclass(frozen=True)
class ScenarioCheckResult:
    requirement: str
    scenario: str
    check_id: str
    status: str
    evidence: str


@dataclass(frozen=True)
class VerifyReport:
    artifact_presence: tuple[str, ...]
    runtime_scope: str
    scenario_coverage: tuple[ScenarioCheckResult, ...]
    rules_compliance: tuple[str, ...]
    verdict: str
    runtime_drift_files: tuple[Path, ...]


def _slugify(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return normalized or "unnamed"


def parse_spec_document(spec_text: str, spec_path: Path) -> ParsedSpec:
    lines = spec_text.splitlines()
    requirements: list[ParsedRequirement] = []

    requirement_name: str | None = None
    requirement_lines: list[str] = []
    scenario_name: str | None = None
    scenario_lines: list[str] = []
    scenarios: list[ParsedScenario] = []
    scenario_sequence = 0

    def flush_scenario() -> None:
        nonlocal scenario_name, scenario_lines, scenario_sequence
        if requirement_name is None or scenario_name is None:
            return
        scenario_sequence += 1
        check_id = (
            f"SCN-{scenario_sequence:03d}-{_slugify(requirement_name)}-{_slugify(scenario_name)}"
        )
        scenarios.append(
            ParsedScenario(
                requirement_name=requirement_name,
                name=scenario_name.strip(),
                body_lines=tuple(line.strip() for line in scenario_lines if line.strip()),
                check_id=check_id,
                spec_path=spec_path,
            )
        )
        scenario_name = None
        scenario_lines = []

    def flush_requirement() -> None:
        nonlocal requirement_name, requirement_lines, scenarios
        flush_scenario()
        if requirement_name is None:
            return
        requirements.append(
            ParsedRequirement(
                name=requirement_name.strip(),
                statement=" ".join(line.strip() for line in requirement_lines if line.strip()),
                scenarios=tuple(scenarios),
                spec_path=spec_path,
            )
        )
        requirement_name = None
        requirement_lines = []
        scenarios = []

    for line in lines:
        if line.startswith("### Requirement:"):
            flush_requirement()
            requirement_name = line.replace("### Requirement:", "", 1).strip()
            continue
        if line.startswith("#### Scenario:"):
            flush_scenario()
            scenario_name = line.replace("#### Scenario:", "", 1).strip()
            continue

        if scenario_name is not None:
            scenario_lines.append(line)
            continue

        if requirement_name is not None:
            requirement_lines.append(line)

    flush_requirement()
    return ParsedSpec(spec_path=spec_path, requirements=tuple(requirements))


def validate_rules_compliance(parsed_specs: list[ParsedSpec]) -> list[str]:
    violations: list[str] = []

    for parsed_spec in parsed_specs:
        for requirement in parsed_spec.requirements:
            if not RFC_2119_PATTERN.search(requirement.statement):
                violations.append(
                    f"RFC 2119 violation in {parsed_spec.spec_path}: requirement '{requirement.name}' "
                    "must include MUST/SHALL/SHOULD/MAY"
                )

            for scenario in requirement.scenarios:
                normalized_lines = [line.upper() for line in scenario.body_lines]
                has_given = any(line.startswith("- GIVEN") for line in normalized_lines)
                has_when = any(line.startswith("- WHEN") for line in normalized_lines)
                has_then = any(line.startswith("- THEN") for line in normalized_lines)
                if not (has_given and has_when and has_then):
                    violations.append(
                        f"Given/When/Then violation in {parsed_spec.spec_path}: scenario '{scenario.name}'"
                    )

                if not scenario.name.strip() or not scenario.check_id.strip():
                    violations.append(
                        f"Scenario mapping violation in {parsed_spec.spec_path}: scenario missing name/check id"
                    )

    return sorted(violations)


def classify_runtime_drift(change_name: str, changed_files: list[Path]) -> list[Path]:
    allowed_prefix = Path("openspec") / "changes" / change_name
    runtime_files: list[Path] = []
    for changed_file in changed_files:
        is_in_change = changed_file.parts[: len(allowed_prefix.parts)] == allowed_prefix.parts
        is_markdown = changed_file.suffix.lower() == ".md"
        if not is_in_change or not is_markdown:
            runtime_files.append(changed_file)
    return sorted(runtime_files)


def _load_verify_rules(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / "openspec" / "config.yaml"
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    rules = raw_config.get("rules", {}) if isinstance(raw_config, dict) else {}
    verify_rules = rules.get("verify", {}) if isinstance(rules, dict) else {}
    return verify_rules if isinstance(verify_rules, dict) else {}


def _collect_change_files(change_path: Path, repo_root: Path) -> list[Path]:
    return [path.relative_to(repo_root) for path in sorted(change_path.rglob("*")) if path.is_file()]


def _check_artifact_presence(change_path: Path, repo_root: Path) -> tuple[list[str], list[Path], list[Path]]:
    required_artifacts = [
        change_path / "proposal.md",
        change_path / "design.md",
        change_path / "tasks.md",
    ]
    required_specs = sorted((change_path / "specs").glob("*/spec.md"))

    messages: list[str] = []
    missing_paths: list[Path] = []
    for artifact in required_artifacts:
        relative = artifact.relative_to(repo_root)
        if artifact.exists():
            messages.append(f"PASS {relative}")
        else:
            messages.append(f"FAIL missing {relative}")
            missing_paths.append(relative)

    if required_specs:
        for spec_path in required_specs:
            messages.append(f"PASS {spec_path.relative_to(repo_root)}")
    else:
        spec_dir = (change_path / "specs").relative_to(repo_root)
        messages.append(f"FAIL missing spec files under {spec_dir}/*/spec.md")
        missing_paths.append(change_path / "specs")

    return messages, missing_paths, required_specs


def _build_scenario_results(parsed_specs: list[ParsedSpec]) -> list[ScenarioCheckResult]:
    results: list[ScenarioCheckResult] = []
    for parsed_spec in parsed_specs:
        for requirement in parsed_spec.requirements:
            for scenario in requirement.scenarios:
                results.append(
                    ScenarioCheckResult(
                        requirement=requirement.name,
                        scenario=scenario.name,
                        check_id=scenario.check_id,
                        status="PASS",
                        evidence=f"Parsed from {parsed_spec.spec_path}",
                    )
                )
    return sorted(results, key=lambda item: item.check_id)


def _render_markdown_report(report: VerifyReport, verify_rules: dict[str, Any], change_name: str) -> str:
    required_sections = verify_rules.get(
        "required_report_sections",
        ["artifact presence", "scenario coverage", "rules compliance", "overall verdict"],
    )
    section_line = ", ".join(str(section) for section in required_sections)

    lines: list[str] = [
        f"# OpenSpec Verification Report: {change_name}",
        "",
        "## Artifact Presence",
        *[f"- {message}" for message in report.artifact_presence],
        "",
        "## Runtime Scope",
        f"- {report.runtime_scope}",
    ]

    if report.runtime_drift_files:
        lines.append("- Runtime drift files detected:")
        lines.extend(f"  - {path}" for path in report.runtime_drift_files)

    lines.extend(
        [
            "",
            "## Scenario Coverage",
            *[
                f"- {row.check_id} | {row.status} | {row.requirement} :: {row.scenario}"
                for row in report.scenario_coverage
            ],
            "",
            "## Rules Compliance",
            *[f"- {message}" for message in report.rules_compliance],
            "",
            "## Overall Verdict",
            f"- {report.verdict}",
            "",
            "## Required Sections",
            f"- {section_line}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_json_report(report: VerifyReport, change_name: str) -> dict[str, Any]:
    return {
        "change_name": change_name,
        "verdict": report.verdict,
        "runtime_scope": report.runtime_scope,
        "summary": {
            "artifact_presence_count": len(report.artifact_presence),
            "scenario_coverage_count": len(report.scenario_coverage),
            "rules_compliance_count": len(report.rules_compliance),
            "runtime_drift_file_count": len(report.runtime_drift_files),
        },
        "artifact_presence": list(report.artifact_presence),
        "scenario_coverage": [
            {
                "requirement": row.requirement,
                "scenario": row.scenario,
                "check_id": row.check_id,
                "status": row.status,
                "evidence": row.evidence,
            }
            for row in report.scenario_coverage
        ],
        "rules_compliance": list(report.rules_compliance),
        "runtime_drift_files": [str(path) for path in report.runtime_drift_files],
    }


def verify_change(verify_input: VerifyInput) -> tuple[int, VerifyReport, str]:
    verify_rules = _load_verify_rules(verify_input.repo_root)
    change_path = verify_input.repo_root / "openspec" / "changes" / verify_input.change_name

    artifact_presence, missing_paths, spec_files = _check_artifact_presence(
        change_path=change_path,
        repo_root=verify_input.repo_root,
    )

    parsed_specs = [
        parse_spec_document(
            spec_text=spec_file.read_text(encoding="utf-8"),
            spec_path=spec_file.relative_to(verify_input.repo_root),
        )
        for spec_file in spec_files
    ]
    scenario_results = _build_scenario_results(parsed_specs)
    rules_violations = validate_rules_compliance(parsed_specs)
    rules_compliance_messages = ["PASS all configured rule checks"]
    if rules_violations:
        rules_compliance_messages = [f"FAIL {violation}" for violation in rules_violations]

    changed_files = _collect_change_files(change_path=change_path, repo_root=verify_input.repo_root)
    runtime_drift_files = classify_runtime_drift(
        change_name=verify_input.change_name,
        changed_files=changed_files,
    )
    runtime_scope = "RUNTIME_DETECTED" if runtime_drift_files else "PROCESS_ONLY"

    verdict = "PASS"
    exit_code = EXIT_OK
    if runtime_drift_files:
        verdict = "FAIL"
        exit_code = EXIT_RUNTIME_DRIFT
        escalation_message = (
            verify_rules.get("runtime_drift", {}).get("escalation_message")
            if isinstance(verify_rules.get("runtime_drift"), dict)
            else None
        )
        if isinstance(escalation_message, str) and escalation_message:
            rules_compliance_messages.append(f"FAIL {escalation_message}")
    elif missing_paths or rules_violations:
        verdict = "FAIL"
        exit_code = EXIT_NON_COMPLIANT

    report = VerifyReport(
        artifact_presence=tuple(artifact_presence),
        runtime_scope=runtime_scope,
        scenario_coverage=tuple(scenario_results),
        rules_compliance=tuple(rules_compliance_messages),
        verdict=verdict,
        runtime_drift_files=tuple(runtime_drift_files),
    )

    markdown = _render_markdown_report(
        report=report,
        verify_rules=verify_rules,
        change_name=verify_input.change_name,
    )
    return exit_code, report, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify docs-only OpenSpec change compliance")
    parser.add_argument("--change", required=True, help="OpenSpec change name under openspec/changes")
    parser.add_argument(
        "--repo-root",
        help="Optional repository root override (used by integration tests)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    exit_code, _report, markdown = verify_change(
        VerifyInput(change_name=args.change, repo_root=repo_root)
    )

    report_path = repo_root / "openspec" / "changes" / args.change / "verify-report.md"
    json_report_path = repo_root / "openspec" / "changes" / args.change / "verify-report.json"
    report_path.write_text(markdown, encoding="utf-8")
    json_report_path.write_text(
        json.dumps(_render_json_report(report=_report, change_name=args.change), indent=2),
        encoding="utf-8",
    )
    print(f"OpenSpec verification report: {report_path.relative_to(repo_root)}")
    if exit_code == EXIT_RUNTIME_DRIFT:
        print("Runtime drift detected. Full verification gates are required.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
