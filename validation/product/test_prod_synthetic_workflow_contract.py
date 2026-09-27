"""Static safety contract for the #715 production acceptance workflow."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "prod-synthetic-acceptance.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_is_manual_only() -> None:
    source = _source()
    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "pull_request:" not in source
    assert "push:" not in source


def test_observed_shas_are_not_operator_self_assertions() -> None:
    source = _source()
    assert (
        "PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA: ${{ inputs.backend_commit_sha }}"
        not in source
    )
    assert (
        "PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA: ${{ inputs.frontend_commit_sha }}"
        not in source
    )
    assert "verify_prod_deployment_identity.py" in source
    assert "PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA: ${{ env.PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA }}" in source
    assert "PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA: ${{ env.PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA }}" in source


def test_provider_identity_is_checked_before_browser_mutation() -> None:
    source = _source()
    observe = source.index("Observe production deployment identities from providers")
    verify = source.index("Verify independently observed deployment identities")
    browser = source.index("Execute real production browser journey")
    assert observe < verify < browser


def test_all_backend_runtime_roles_are_provider_verified() -> None:
    source = _source()
    assert "PROD_ACCEPTANCE_RAILWAY_API_SERVICE_ID" in source
    assert "PROD_ACCEPTANCE_RAILWAY_WORKER_SERVICE_ID" in source
    assert "PROD_ACCEPTANCE_RAILWAY_SCHEDULER_SERVICE_ID" in source
    assert "--railway-api-json" in source
    assert "--railway-worker-json" in source
    assert "--railway-scheduler-json" in source


def test_issue_690_credentials_fail_closed_before_browser_mutation() -> None:
    source = _source()
    gate = source.index("Fail closed on protected qualification prerequisites")
    browser = source.index("Execute real production browser journey")
    assert gate < browser
    for secret in (
        "PROD_ACCEPTANCE_CLERK_EMAIL",
        "PROD_ACCEPTANCE_CLERK_PASSWORD",
        "PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID",
        "PROD_ACCEPTANCE_EXPECTED_TENANT_ID",
    ):
        assert secret in source


def test_raw_provider_responses_are_not_uploaded_as_qualification_artifacts() -> None:
    source = _source()
    upload = source[source.index("Upload bounded qualification artifacts") :]
    assert "runtime/provider/" not in upload
    assert "runtime/deployment-identity.json" in upload


def test_production_environment_and_explicit_operator_intent_remain_required() -> None:
    source = _source()
    assert "environment: production-qualification" in source
    assert 'test "${{ inputs.confirm_production }}" = "RUN-ISSUE-706"' in source
    assert 'test "${{ inputs.railway_staged_changes_clear }}" = "true"' in source
