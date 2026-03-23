"""TS-SEC-CI-GLK-001

Regression checks for gitleaks integration in CI.
"""

from __future__ import annotations

from pathlib import Path


def test_tests_workflow_runs_gitleaks_scan() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "tests.yml"
    contents = workflow.read_text(encoding="utf-8")

    assert "name: Secrets Scan" in contents
    assert "gitleaks/gitleaks-action@v2" in contents
    assert "needs: [secrets-scan, s5-core-ai-gates, unit-tests, integration-tests]" in contents
