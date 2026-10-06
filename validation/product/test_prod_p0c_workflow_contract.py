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
NO_CHANGE_FIXTURE_BUILDER = (
    REPO_ROOT / "apps/api/scripts/build_p0c_semantic_no_change_fixture.py"
)


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_p0c_workflow_is_owner_comment_only_and_uses_protected_environment() -> None:
    source = _workflow()
    assert "issue_comment:" in source
    assert "types: [created]" in source
    assert "workflow_dispatch:" not in source
    assert "workflow_call:" not in source
    assert "schedule:" not in source
    assert "actions: write" not in source
    assert "github.event.issue.number == 686" in source
    assert "github.event.comment.user.login == github.repository_owner" in source
    assert "github.triggering_actor == github.repository_owner" in source
    assert "startsWith(github.event.comment.body, 'RUN-ISSUE-686 ')" in source
    assert "environment: production-qualification" in source
    assert 'test "$CONFIRM" = "RUN-ISSUE-686"' in source
    assert 'test "${GITHUB_REF_NAME}" = "main"' in source


def test_p0c_workflow_fails_closed_before_product_mutation() -> None:
    source = _workflow()
    fixture = source.index("Build byte-distinct semantic no-change fixture")
    preflight = source.index("Fail closed if accepted P0b project is no longer clean")
    browser = source.index("Execute real P0c production browser journey")
    post = source.index("Read-only durable post-run P0c verification")
    bundle = source.index("Build non-authoritative P0c evidence bundle")
    validator = source.index("Validate canonical qualification evidence contract")
    assert fixture < preflight < browser < post < bundle < validator
    assert "--source-revision-id" in source
    assert "--target-revision-id" in source
    assert "--write-evidence" in source


def test_p0c_workflow_propagates_observed_runtime_identity_to_browser_preflight() -> None:
    source = _workflow()
    assert 'deployment-identity.json"))["backend"]["api"]["commit_sha"]' in source
    assert 'deployment-identity.json"))["frontend"]["commit_sha"]' in source
    assert "id: runtime_identity" in source
    assert 'backend_sha=$backend_sha' in source
    assert 'frontend_sha=$frontend_sha' in source
    assert '>> "$GITHUB_OUTPUT"' in source

    preflight = source.split("Non-mutating real production identity preflight", 1)[1].split(
        "Fail closed if accepted P0b project is no longer clean", 1
    )[0]
    assert "PROD_ACCEPTANCE_EXPECTED_BACKEND_SHA:" in preflight
    assert (
        "PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA: "
        "${{ steps.runtime_identity.outputs.backend_sha }}"
    ) in preflight
    assert "PROD_ACCEPTANCE_EXPECTED_FRONTEND_SHA:" in preflight
    assert (
        "PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA: "
        "${{ steps.runtime_identity.outputs.frontend_sha }}"
    ) in preflight
    assert "${{ env.PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA }}" not in preflight
    assert "${{ env.PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA }}" not in preflight


def test_p0c_provider_observation_resolves_the_serving_frontend_hostname() -> None:
    source = _workflow()
    provider = source.split(
        "Observe production deployment identities from providers", 1
    )[1].split("Verify exact provider deployment identities", 1)[0]
    assert (
        "https://api.vercel.com/v13/deployments/c2pro.io"
        "?teamId=${PROD_ACCEPTANCE_VERCEL_TEAM_ID}"
    ) in provider
    assert (
        "/v13/deployments/${PROD_INPUT_FRONTEND_DEPLOYMENT_ID}?teamId="
        not in provider
    )


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
    assert "PROD_P0C_NO_CHANGE_PDF" in source
    assert "No material change found" in source
    assert "no_change_target_revision_id" in source
    assert "byte-distinct-parser-equivalent" in source
    assert "PROD_P0C_NO_CHANGE_EXPECTED_SHA256" in source
    assert 'createHash("sha256")' in source
    assert "no_change_fixture_sha256" in source


def test_p0c_verifier_is_read_only_and_exactly_revision_bound() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in source
    assert "app.current_tenant" in source
    assert "parent_revision_id=:source_revision_id" in source
    assert "event_type='revision.changed'" in source
    assert "payload->'provenance'->>'source_revision_id'" in source
    assert "payload->'provenance'->>'target_revision_id'" in source
    assert "every reported change carries evidence" in source
    assert "no_change_target_revision_id" in source
    assert "semantic no-change cause key is explicitly persisted as JSON null" in source
    assert "semantic no-change changeset is explicitly persisted as an empty array" in source
    assert "semantic no-change revision is byte-distinct" in source
    assert "payload ? 'change_cause'" in source
    assert "change_cause_type" in source
    assert "(payload->'changeset') ? 'changes'" in source
    assert "changes_type" in source
    assert "persisted semantic no-change revision matches generated Contract C" in source
    assert "no_change_expected_blob_hash" in source


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
    assert '"id": "no-change-target-revision"' in source
    assert '"id": "no-change-event"' in source
    assert "byte-distinct parser-equivalent derivative" in source
    assert '"no_change_fixture_sha256": no_change_blob_hash' in source
    assert '"sha256": no_change_blob_hash' in source


def test_p0c_semantic_no_change_fixture_is_fail_closed_by_construction() -> None:
    source = NO_CHANGE_FIXTURE_BUILDER.read_text(encoding="utf-8")
    assert "import fitz" in source
    assert "original_sha == derived_sha" in source
    assert "_blocks(original) != _blocks(derived)" in source
    assert "PJ01-P0C-NO-CHANGE" in source
    assert "contract-c-semantic-no-change.pdf" in source
    workflow = _workflow()
    assert "PROD_P0C_NO_CHANGE_EXPECTED_SHA256" in workflow
    assert "--no-change-expected-blob-hash" in workflow


def test_p0c_workflow_does_not_interpolate_dispatch_inputs_inside_shell() -> None:
    source = _workflow()
    run_blocks = source.split("run: |")[1:]
    for block in run_blocks:
        shell_body = block.split("\n      - name:", 1)[0]
        assert "${{ inputs." not in shell_body
