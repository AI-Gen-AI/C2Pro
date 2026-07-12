"""TS-SEC-CI-GLK-001

Regression checks for gitleaks integration in CI.

tests.yml (which embedded a duplicate gitleaks-action job) was replaced by
ci.yml in TASK-DEV-003; secret-scan.yml is the single gitleaks gate and runs
on every PR and push.
"""

from __future__ import annotations

from pathlib import Path


def test_secret_scan_workflow_runs_gitleaks_on_prs_and_pushes() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "secret-scan.yml"
    contents = workflow.read_text(encoding="utf-8")

    assert "pull_request:" in contents
    assert "push:" in contents
    assert "gitleaks detect --no-git --config .gitleaks.toml" in contents
    assert "--redact" in contents
    assert "--exit-code 1" in contents
