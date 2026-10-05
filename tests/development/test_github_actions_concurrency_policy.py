"""Regression contracts for PR-scoped GitHub Actions concurrency.

DEV-15 Wave 4: cancel superseded PR runs without cancelling main/develop pushes.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

TARGETS = {
    "install-drift-guard.yml": "install-drift-guard",
    "c2pro-development-control.yml": "c2pro-development-control",
    "c2pro-product-control-guard.yml": "c2pro-product-control-guard",
    "constraints-lock.yml": "constraints-lock",
}


def test_target_workflows_cancel_only_superseded_pull_request_runs() -> None:
    workflows = REPO_ROOT / ".github" / "workflows"

    for filename, group_prefix in TARGETS.items():
        text = (workflows / filename).read_text(encoding="utf-8")

        assert "concurrency:" in text, filename
        assert f"group: {group_prefix}-" in text, filename
        assert "github.event.pull_request.number || github.ref" in text, filename
        assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text, filename
