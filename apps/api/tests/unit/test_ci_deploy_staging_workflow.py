"""TS-CICD-DEPLOY-001

Regression checks for merge-to-main staging deployment automation.
"""

from __future__ import annotations

from pathlib import Path


def test_deploy_staging_workflow_exists_and_targets_main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "deploy-staging.yml"

    assert workflow.exists()

    contents = workflow.read_text(encoding="utf-8")
    assert "name: Deploy Staging" in contents
    assert "branches: [main]" in contents
    assert "deploy-backend:" in contents
    assert "deploy-frontend:" in contents
    assert "environment: staging" in contents
    assert "railway up --service api" in contents
    assert "railway up --service celery-worker" in contents
    assert "vercel deploy --prebuilt" in contents
    assert "needs: [deploy-backend]" in contents
