"""TS-CICD-G7-WF-001

Regression checks for Gate 7 release workflow wiring.

The Actions-driven deploy-production.yml was retired 2026-07-12 (TASK-DEV-003):
deploys are platform-owned (Railway/Vercel auto-deploy pushes to main behind
branch protection), and release.yml provides the auditable release trail —
tag-driven certification plus an environment-gated GitHub Release.
"""

from __future__ import annotations

from pathlib import Path


def _release_workflow() -> str:
    repo_root = Path(__file__).resolve().parents[4]
    return (repo_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")


def test_release_workflow_exists_with_tag_and_dispatch_triggers() -> None:
    contents = _release_workflow()

    assert "name: Release" in contents
    assert 'tags: ["v*"]' in contents
    assert "workflow_dispatch:" in contents
    assert "allow_missing_ci:" in contents


def test_release_workflow_certifies_candidate_before_publishing() -> None:
    contents = _release_workflow()

    assert "git merge-base --is-ancestor" in contents
    assert 'select(.name == "CI Status")' in contents
    assert "python scripts/validate_release_evidence.py" in contents
    assert "evidence/releases/${TAG}" in contents


def test_release_workflow_publish_is_environment_gated_and_needs_certify() -> None:
    contents = _release_workflow()

    assert "environment: Production" in contents
    assert "needs: certify" in contents
    assert "--generate-notes" in contents
    assert "--verify-tag" in contents


def test_gate7_supporting_workflows_publish_release_evidence() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    evaluation_workflow = (repo_root / ".github" / "workflows" / "evaluation-regression.yml").read_text(
        encoding="utf-8"
    )
    reliability_workflow = (repo_root / ".github" / "workflows" / "i13-real-e2e-scheduled.yml").read_text(
        encoding="utf-8"
    )

    assert "evaluation-release-summary" in evaluation_workflow
    assert "release_commit_sha:" in reliability_workflow
    assert "i13-release-summary" in reliability_workflow
    assert "ref: ${{ inputs.release_commit_sha }}" in reliability_workflow
    assert "executed_commit_sha=$(git rev-parse HEAD)" in reliability_workflow


def test_i13_release_summary_uses_env_indirection_for_dispatch_input() -> None:
    """Test Suite ID: TS-CICD-G7-WF-001."""

    repo_root = Path(__file__).resolve().parents[4]
    reliability_workflow = (repo_root / ".github" / "workflows" / "i13-real-e2e-scheduled.yml").read_text(
        encoding="utf-8"
    )

    assert "RELEASE_SHA: ${{ inputs.release_commit_sha }}" in reliability_workflow
    assert 'release_commit_sha="$RELEASE_SHA"' in reliability_workflow
    assert "release_commit_sha=${{ inputs.release_commit_sha }}" not in reliability_workflow
