"""Static safety contracts for the #867 B1-12 production qualification harness."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "prod-b1-12-qualification.yml"
PLAYWRIGHT = REPO_ROOT / "apps" / "web" / "playwright.config.ts"
SPEC = REPO_ROOT / "apps" / "web" / "src" / "tests" / "e2e" / "prod-acceptance" / "867-production-alerts-coherence.spec.ts"
VERIFIER = REPO_ROOT / "apps" / "api" / "scripts" / "verify_b1_12_prod_acceptance.py"
BUNDLE = REPO_ROOT / "validation" / "product" / "build_b1_12_prod_qualification_bundle.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_is_manual_main_only_and_protected() -> None:
    source = _source(WORKFLOW)
    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "environment: production-qualification" in source
    assert "RUN-ISSUE-867" in source
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in source
    assert 'test "$STAGED_CLEAR" = "true"' in source
    assert 'retention-days: 3' in source


def test_workflow_rebinds_runtime_before_browser_mutation() -> None:
    source = _source(WORKFLOW)
    railway = source.index("Observe Railway production identities")
    vercel = source.index("Observe Vercel production identity")
    verify = source.index("Verify independently observed deployment identities")
    browser = source.index("Execute B1-12 real production browser journey")
    assert railway < verify < browser
    assert vercel < verify < browser
    assert "verify_prod_deployment_identity.py" in source
    assert "deployment-identity.json" in source


def test_workflow_uses_bounded_synthetic_tenant_preflight() -> None:
    source = _source(WORKFLOW)
    assert '--allow-project-prefix "ACCEPT-867-"' in source
    assert 'PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED=1' in source
    assert "--database-url" not in source
    assert (
        "PROD_ACCEPTANCE_DATABASE_URL_READONLY: "
        "${{ secrets.PROD_ACCEPTANCE_DATABASE_URL_READONLY }}"
    ) in source


def test_playwright_project_disables_sensitive_recording() -> None:
    source = _source(PLAYWRIGHT)
    start = source.index('name: "prod-b1-12"')
    snippet = source[start : start + 1000]
    assert 'trace: "off"' in snippet
    assert 'screenshot: "off"' in snippet
    assert 'video: "off"' in snippet


def test_structured_documents_settle_before_coherence() -> None:
    source = _source(SPEC)
    assert "B1_BUDGET_NOT_ENQUEUED" in source
    assert "B1_SCHEDULE_NOT_ENQUEUED" in source
    assert "B1_BUDGET_NOT_ANALYZED" in source
    assert "B1_SCHEDULE_NOT_ANALYZED" in source
    assert source.index("B1_SCHEDULE_NOT_ANALYZED") < source.index(
        "const firstEvaluation = await evaluateThroughUi"
    )
    assert 'finding.code !== "DOCUMENT_DUPLICATED"' in source
    assert "B1_PROD_BLOCKING_FINDINGS" in source


def test_verifier_fails_closed_on_missing_family_and_bounds_approval_window() -> None:
    source = _source(VERIFIER)
    assert "finding_key_valid = isinstance(finding_key, str) and bool(finding_key)" in source
    assert "if finding_key_valid" in source
    assert "if approve_at and source_result and rescore_result:" in source
    assert 'rescore_at = rescore_result["calculated_at"]' in source
    assert 'source_at < row["calculated_at"] < rescore_at' in source


def test_bundle_requires_complete_browser_verifier_identity_parity() -> None:
    source = _source(BUNDLE)
    assert 'browser/verifier project mismatch' in source
    assert 'browser/verifier false-positive alert mismatch' in source
    assert 'browser/verifier genuine alert mismatch' in source
    assert 'browser/verifier post-revision false-positive alert mismatch' in source


def test_workflow_binds_real_b1_harness_and_independent_validator() -> None:
    source = _source(WORKFLOW)
    assert "generate_b1_prod_qualification_fixtures.py" in source
    assert "867-production-alerts-coherence.spec.ts" in source
    assert "verify_b1_12_prod_acceptance.py" in source
    assert "build_b1_12_prod_qualification_bundle.py" in source
    assert "validate_b1_12_prod_qualification.py" in source
    assert "RUN-ISSUE-706" not in source


def test_raw_provider_payloads_are_not_uploaded() -> None:
    source = _source(WORKFLOW)
    upload = source[source.index("Upload bounded B1-12 artifacts") :]
    assert "runtime/provider/" not in upload
    assert "runtime/deployment-identity.json" in upload
