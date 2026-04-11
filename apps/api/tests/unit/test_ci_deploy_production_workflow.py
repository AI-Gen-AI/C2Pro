"""TS-CICD-G7-WF-001

Regression checks for Gate 7 production release workflow wiring.
"""

from __future__ import annotations

from pathlib import Path


def test_deploy_production_workflow_exists_and_validates_gate7_bundle() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "deploy-production.yml"

    assert workflow.exists()

    contents = workflow.read_text(encoding="utf-8")
    assert "name: Deploy Production" in contents
    assert "workflow_dispatch:" in contents
    assert "environment: production" in contents
    assert "release_id:" in contents
    assert "commit_sha:" in contents
    assert "python scripts/validate_release_evidence.py" in contents
    assert "railway up --service api" in contents
    assert "railway up --service celery-worker" in contents
    assert "vercel deploy --prebuilt --prod" in contents


def test_gate7_workflows_publish_release_summary_artifacts_and_release_dispatch() -> None:
    repo_root = Path(__file__).resolve().parents[4]

    tests_workflow = (repo_root / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    frontend_workflow = (repo_root / ".github" / "workflows" / "frontend-ci.yml").read_text(encoding="utf-8")
    security_workflow = (repo_root / ".github" / "workflows" / "e2e-security-tests.yml").read_text(encoding="utf-8")
    evaluation_workflow = (repo_root / ".github" / "workflows" / "evaluation-regression.yml").read_text(encoding="utf-8")
    reliability_workflow = (repo_root / ".github" / "workflows" / "i13-real-e2e-scheduled.yml").read_text(encoding="utf-8")

    assert "backend-release-summary" in tests_workflow
    assert "frontend-release-summary" in frontend_workflow
    assert "security-release-summary" in security_workflow
    assert "evaluation-release-summary" in evaluation_workflow
    assert "release_commit_sha:" in reliability_workflow
    assert "i13-release-summary" in reliability_workflow
    assert "github.event_name == 'workflow_dispatch'" in reliability_workflow


def test_deploy_production_workflow_dispatches_release_reliability_for_candidate_sha() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = (repo_root / ".github" / "workflows" / "deploy-production.yml").read_text(encoding="utf-8")

    assert "dispatch-release-reliability:" in workflow
    assert "gh workflow run i13-real-e2e-scheduled.yml" in workflow
    assert 'release_commit_sha="${{ inputs.commit_sha }}"' in workflow
    assert "needs: [validate-release, dispatch-release-reliability]" in workflow


def test_i13_release_dispatch_checks_out_release_candidate_sha() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    reliability_workflow = (repo_root / ".github" / "workflows" / "i13-real-e2e-scheduled.yml").read_text(
        encoding="utf-8"
    )

    assert "ref: ${{ inputs.release_commit_sha }}" in reliability_workflow


def test_deploy_production_workflow_waits_for_reliability_run_and_downloads_summary() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = (repo_root / ".github" / "workflows" / "deploy-production.yml").read_text(encoding="utf-8")

    assert "gh run watch" in workflow
    assert "gh run download" in workflow
    assert "i13-release-summary" in workflow


def test_i13_release_summary_records_candidate_and_executed_sha() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    reliability_workflow = (repo_root / ".github" / "workflows" / "i13-real-e2e-scheduled.yml").read_text(
        encoding="utf-8"
    )

    assert "release_commit_sha=${{ inputs.release_commit_sha }}" in reliability_workflow
    assert "executed_commit_sha=$(git rev-parse HEAD)" in reliability_workflow
