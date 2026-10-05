"""Static fail-closed contracts for the #686 P0c production workflow."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/prod-p0c-qualification.yml"
SPEC = (
    REPO_ROOT
    / "apps/web/src/tests/e2e/prod-acceptance/686-p0c-production.spec.ts"
)
VERIFIER = REPO_ROOT / "apps/api/scripts/verify_p0c_prod_journey.py"
BUILDER = REPO_ROOT / "validation/product/build_p0c_prod_qualification_bundle.py"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_p0c_workflow_is_manual_and_uses_protected_environment() -> None:
    source = _workflow()
    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "environment: production-qualification" in source
    assert 'test "$CONFIRM" = "RUN-ISSUE-686"' in source
    assert 'test "${GITHUB_REF_NAME}" = "main"' in source


def test_p0c_workflow_fails_closed_before_product_mutation() -> None:
    source = _workflow()
    preflight = source.index("Fail closed if accepted P0b project is no longer clean")
    browser = source.index("Execute real P0c production browser journey")
    post = source.index("Read-only durable post-run P0c verification")
    bundle = source.index("Build non-authoritative P0c evidence bundle")
    validator = source.index("Validate canonical qualification evidence contract")
    assert preflight < browser < post < bundle < validator
    assert "--source-revision-id" in source
    assert "--target-revision-id" in source
    assert "--write-evidence" in source


def test_p0c_workflow_uses_only_protected_qualification_credentials() -> None:
    source = _workflow()
    for secret in (
        "PROD_ACCEPTANCE_RAILWAY_API_TOKEN",
        "PROD_ACCEPTANCE_VERCEL_TOKEN",
        "PROD_ACCEPTANCE_DATABASE_URL_READONLY",
        "PROD_ACCEPTANCE_EXPECTED_TENANT_ID",
        "PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID",
        "PROD_ACCEPTANCE_CLERK_EMAIL",
        "PROD_ACCEPTANCE_CLERK_PASSWORD",
    ):
        assert f"secrets.{secret}" in source
    assert "PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED=1" in source


def test_p0c_browser_reuses_canonical_revision_and_what_changed_helpers() -> None:
    source = SPEC.read_text(encoding="utf-8")
    assert "signInSyntheticProductionUser(page)" in source
    assert "uploadNewVersionThroughUi" in source
    assert "observeProcessingWithoutReload" in source
    assert "assertWhatChangedThroughNavigation" in source
    assert "signOutThroughUi(page)" in source
    assert "documentsListed" in source
    assert "expectedSourceRevisionId" in source


def test_p0c_verifier_is_read_only_and_exactly_revision_bound() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in source
    assert "app.current_tenant" in source
    assert "parent_revision_id=:source_revision_id" in source
    assert "event_type='revision.changed'" in source
    assert "payload->'provenance'->>'source_revision_id'" in source
    assert "payload->'provenance'->>'target_revision_id'" in source
    assert "every reported change carries evidence" in source


def test_p0c_bundle_uses_canonical_phase_a_contract_without_lifecycle_authority() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    assert '"capability_id": "P0c"' in source
    assert '"lifecycle_authority": False' in source
    for assertion in (
        "durable_revision_bound_events",
        "timeline_queryable",
        "semantic_change_source_traceable",
        "api_ui_projection_parity",
        "absent_evidence_does_not_invent_change",
    ):
        assert f'"id": "{assertion}"' in source
