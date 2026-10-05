from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/p0c-production-qualification.yml"
SPEC = ROOT / "apps/web/src/tests/e2e/prod-acceptance/686-p0c-production.spec.ts"
VERIFIER = ROOT / "apps/api/scripts/verify_p0c_prod_qualification.py"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_p0c_production_workflow_is_manual_and_environment_gated() -> None:
    source = _workflow()
    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "environment: production-qualification" in source
    assert 'test "$CONFIRM" = "RUN-ISSUE-686"' in source
    assert 'test "${GITHUB_REF_NAME}" = "main"' in source
    assert 'test "$STAGED_CLEAR" = "true"' in source


def test_p0c_workflow_binds_exact_runtime_and_existing_document() -> None:
    source = _workflow()
    for required in (
        "backend_commit_sha:",
        "backend_deployment_id:",
        "frontend_commit_sha:",
        "frontend_deployment_id:",
        "project_id:",
        "document_id:",
        "source_revision_id:",
        "verify_prod_deployment_identity.py",
        "verify_p0c_prod_qualification.py",
        "build_p0c_prod_qualification_bundle.py",
        "validate_qualification_evidence.py",
    ):
        assert required in source


def test_p0c_browser_journey_only_uploads_new_version() -> None:
    source = SPEC.read_text(encoding="utf-8")
    assert "uploadNewVersionThroughUi" in source
    assert "uploadDocumentThroughUi" not in source
    assert "createProjectThroughUi" not in source
    assert "signInSyntheticProductionUser" in source
    assert "signOutThroughUi" in source
    assert "assertWhatChangedThroughNavigation" in source
    assert "documentsListed !== 1" in source


def test_p0c_verifier_is_read_only_and_tenant_scoped() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in source
    assert "app.current_tenant" in source
    assert "UPDATE " not in source
    assert "DELETE " not in source
    assert "INSERT " not in source
    assert "event_type = \'revision.changed\'" in source
    assert "jsonb_array_length(evidence_refs) > 0" in source
