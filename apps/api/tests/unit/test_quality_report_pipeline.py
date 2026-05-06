"""Quality report pipeline contract tests.

Test Suite ID: TS-QA-CONTRACT-COVERAGE-TRACK-C-001
Backlog: TASK-QA-212, TASK-QA-213
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_quality_report_cli_renders_markdown_summary(tmp_path: Path) -> None:
    """TS-QA-CONTRACT-COVERAGE-TRACK-C-001: CLI renders all quality gates."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "quality_report.py"
    contract = tmp_path / "contract-coverage.json"
    wireframe = tmp_path / "wireframe-coverage.json"
    coverage = tmp_path / "coverage.xml"
    junit = tmp_path / "unit.xml"
    output = tmp_path / "quality-report.md"

    contract.write_text(
        json.dumps(
            {
                "total_operations": 56,
                "covered_operations": 54,
                "coverage_percent": 96.43,
            }
        ),
        encoding="utf-8",
    )
    wireframe.write_text(
        json.dumps(
            {
                "total_wireframes": 6,
                "covered": 6,
                "uncovered": 0,
                "coverage_pct": 100,
            }
        ),
        encoding="utf-8",
    )
    coverage.write_text(
        '<coverage line-rate="0.8125" branch-rate="0.70"></coverage>',
        encoding="utf-8",
    )
    junit.write_text(
        '<testsuite tests="10" failures="1" errors="0" skipped="2"></testsuite>',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--contract-coverage",
            str(contract),
            "--wireframe-coverage",
            str(wireframe),
            "--coverage-xml",
            str(coverage),
            "--junit-xml",
            str(junit),
            "--output",
            str(output),
            "--base-contract-coverage",
            "97.0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = output.read_text(encoding="utf-8")
    assert "## C2Pro Quality Gate Report" in report
    assert "| Contract coverage | 96.43% | 54/56 operations |" in report
    assert "| Wireframe coverage | 100.00% | 6/6 wireframes |" in report
    assert "| Python coverage | 81.25% | coverage.xml |" in report
    assert "| JUnit results | 70.00% | 7/10 passed, 1 failed, 0 errors, 2 skipped |" in report
    assert "Contract coverage delta vs base: -0.57%" in report


def test_quality_report_cli_fails_when_contract_coverage_drops_too_far(tmp_path: Path) -> None:
    """TS-QA-CONTRACT-COVERAGE-TRACK-C-001: main PRs fail on >2% contract drops."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "quality_report.py"
    contract = tmp_path / "contract-coverage.json"
    output = tmp_path / "quality-report.md"

    contract.write_text(
        json.dumps({"total_operations": 56, "covered_operations": 50, "coverage_percent": 89.29}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--contract-coverage",
            str(contract),
            "--output",
            str(output),
            "--base-contract-coverage",
            "93.0",
            "--fail-on-contract-drop",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Contract coverage dropped by 3.71%" in result.stderr
    assert output.exists()


def test_quality_report_action_and_workflows_are_wired() -> None:
    """TS-QA-CONTRACT-COVERAGE-TRACK-C-001: composite action is wired into CI."""
    repo_root = Path(__file__).resolve().parents[4]
    action = repo_root / ".github" / "actions" / "quality-report" / "action.yml"
    tests_workflow = (repo_root / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    frontend_workflow = (repo_root / ".github" / "workflows" / "frontend-ci.yml").read_text(encoding="utf-8")
    qa_swarm_workflow = (repo_root / ".github" / "workflows" / "qa-swarm.yml").read_text(encoding="utf-8")

    assert action.exists()
    action_text = action.read_text(encoding="utf-8")
    assert "scripts/quality_report.py" in action_text
    assert "quality-report.md" in action_text
    assert "contract-coverage-json" in action_text
    assert "wireframe-coverage-json" in action_text

    for workflow_text in [tests_workflow, frontend_workflow, qa_swarm_workflow]:
        assert "./.github/actions/quality-report" in workflow_text
        assert "marocchino/sticky-pull-request-comment" in workflow_text
        assert "quality-report.md" in workflow_text
