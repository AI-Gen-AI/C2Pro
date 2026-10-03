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


def test_railway_provider_supports_both_documented_token_headers_and_fails_closed() -> None:
    source = _source()
    provider = source[
        source.index("Observe production deployment identities from providers") :
        source.index("Verify independently observed deployment identities")
    ]
    assert '"Authorization"' in provider
    assert '"Project-Access-Token"' in provider
    assert "Railway provider observation failed for all supported token authentication modes." in provider
    assert "(.errors // [])" in provider
    assert "serviceInstance(serviceId:" in provider


def test_provider_identity_is_checked_before_browser_mutation() -> None:
    source = _source()
    observe = source.index("Observe production deployment identities from providers")
    verify = source.index("Verify independently observed deployment identities")
    browser = source.index("Execute real production browser journey")
    assert observe < verify < browser


def test_all_backend_runtime_roles_are_provider_verified() -> None:
    source = _source()
    assert '"api:${PROD_ACCEPTANCE_RAILWAY_API_SERVICE_ID}"' in source
    assert '"worker:${PROD_ACCEPTANCE_RAILWAY_WORKER_SERVICE_ID}"' in source
    assert '"scheduler:${PROD_ACCEPTANCE_RAILWAY_SCHEDULER_SERVICE_ID}"' in source
    assert '"evidence/product-qualification/runtime/provider/railway-${name}.json"' in source
    assert '"api:${PROD_ACCEPTANCE_RAILWAY_API_SERVICE_ID}"' in source
    assert '"worker:${PROD_ACCEPTANCE_RAILWAY_WORKER_SERVICE_ID}"' in source
    assert '"scheduler:${PROD_ACCEPTANCE_RAILWAY_SCHEDULER_SERVICE_ID}"' in source
    assert "--railway-api-json" not in source
    assert "--railway-worker-json" not in source
    assert "--railway-scheduler-json" not in source


def test_issue_690_credentials_fail_closed_before_browser_mutation() -> None:
    source = _source()
    gate = source.index("Fail closed on protected qualification prerequisites")
    browser = source.index("Execute real production browser journey")
    assert gate < browser
    for prerequisite_name in (
        "PROD_ACCEPTANCE_CLERK_EMAIL",
        "PROD_ACCEPTANCE_CLERK_PASSWORD",
        "PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID",
        "PROD_ACCEPTANCE_EXPECTED_TENANT_ID",
    ):
        assert prerequisite_name in source


def test_raw_provider_responses_are_not_uploaded_as_qualification_artifacts() -> None:
    source = _source()
    upload = source[source.index("Upload bounded qualification artifacts") :]
    assert "runtime/provider/" not in upload
    assert "runtime/deployment-identity.json" in upload


def test_production_environment_and_explicit_operator_intent_remain_required() -> None:
    source = _source()
    assert "environment: production-qualification" in source
    assert 'test "$PROD_INPUT_CONFIRM_PRODUCTION" = "RUN-ISSUE-706"' in source
    assert 'test "$PROD_INPUT_RAILWAY_STAGED_CHANGES_CLEAR" = "true"' in source



def test_dispatch_inputs_are_not_interpolated_directly_into_shell_source() -> None:
    source = _source()
    lines = source.splitlines()
    run_sources: list[str] = []

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not stripped.startswith("run:"):
            index += 1
            continue

        inline = stripped.removeprefix("run:").strip()
        if inline and inline != "|":
            run_sources.append(inline)
            index += 1
            continue

        index += 1
        block: list[str] = []
        while index < len(lines):
            candidate = lines[index]
            candidate_stripped = candidate.lstrip()
            candidate_indent = len(candidate) - len(candidate_stripped)
            if candidate_stripped and candidate_indent <= indent:
                break
            block.append(candidate)
            index += 1
        run_sources.append("\n".join(block))

    assert run_sources
    assert all("${{ inputs." not in block for block in run_sources)


def test_identity_preflight_has_explicit_bounded_test_timeout() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-identity-preflight.spec.ts"
    ).read_text(encoding="utf-8")
    assert "IDENTITY_PREFLIGHT_TIMEOUT_MS = 5 * 60_000" in spec
    assert "test.setTimeout(IDENTITY_PREFLIGHT_TIMEOUT_MS)" in spec


def test_prod_auth_signout_selector_matches_application_header() -> None:
    helper = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "support"
        / "prod-auth.synthetic.ts"
    ).read_text(encoding="utf-8")
    header = (
        REPO_ROOT
        / "apps"
        / "web"
        / "components"
        / "layout"
        / "AppHeader.tsx"
    ).read_text(encoding="utf-8")

    assert 'aria-label="User menu"' in header
    assert "Sign out" in header
    assert 'name: /user menu/i' in helper
    assert 'name: /sign out/i' in helper


def test_prod_auth_observes_the_browser_canonical_production_origin() -> None:
    helper = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "support"
        / "prod-auth.synthetic.ts"
    ).read_text(encoding="utf-8")

    configured = helper.index("const configuredOrigin = requireProductionOrigin(productionBaseUrl());")
    goto_sign_in = helper.index("await page.goto(`${configuredOrigin}/sign-in`);", configured)
    canonical = helper.index("const baseOrigin = requireProductionOrigin(page.url());", goto_sign_in)
    observer = helper.index("const observed = observeApplicationAuth(page, baseOrigin);", canonical)

    assert configured < goto_sign_in < canonical < observer


def test_prod_auth_proves_real_clerk_session_before_protected_navigation() -> None:
    helper = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "support"
        / "prod-auth.synthetic.ts"
    ).read_text(encoding="utf-8")

    assert "@clerk/testing" not in helper
    submit = helper.index(
        'page.getByRole("button", { name: /^continue$/i }).click();',
        helper.index('input[name="password"]'),
    )
    signed_in = helper.index("await waitForSignedInClerkUser(page);", submit)
    protected_navigation = helper.index(
        "await page.goto(`${baseOrigin}/projects`);",
        signed_in,
    )
    organization = helper.index(
        "await waitForActiveOrganization(page);",
        protected_navigation,
    )

    assert submit < signed_in < protected_navigation < organization
    assert "PROD_ACCEPTANCE_CLERK_SESSION_NOT_ACTIVE" in helper
    assert "PROD_ACCEPTANCE_CLERK_ORGANIZATION_NOT_ACTIVE" in helper


def test_identity_preflight_is_the_default_non_mutating_mode() -> None:
    source = _source()
    assert 'default: "identity-preflight"' in source
    identity = source.index("Execute non-mutating real production identity preflight")
    journey = source.index("Execute real production browser journey")
    assert identity < journey
    assert "706-production-identity-preflight.spec.ts" in source


def test_product_mutation_and_postrun_steps_require_full_journey_mode() -> None:
    source = _source()
    full_gate = "if: ${{ inputs.execution_mode == 'full-journey' }}"
    for step in (
        "Execute real production browser journey",
        "Resolve bounded run identifiers",
        "Read-only durable post-run verification",
        "Build non-authoritative P0b evidence bundle",
        "Validate qualification evidence contract",
    ):
        start = source.index(f"- name: {step}")
        snippet = source[start : start + 220]
        assert full_gate in snippet, f"{step} is not gated to full-journey mode"


def test_production_playwright_projects_disable_sensitive_artifacts() -> None:
    config = (REPO_ROOT / "apps" / "web" / "playwright.config.ts").read_text(
        encoding="utf-8"
    )
    for project in ("prod-identity-preflight", "prod-acceptance"):
        start = config.index(f'name: "{project}"')
        snippet = config[start : start + 700]
        assert 'trace: "off"' in snippet
        assert 'screenshot: "off"' in snippet
        assert 'video: "off"' in snippet
        assert "recordHar" not in snippet


def test_provider_observation_is_bound_to_canonical_service_and_environment_ids() -> None:
    source = _source()
    provider = source[
        source.index("Observe production deployment identities from providers") :
        source.index("Verify independently observed deployment identities")
    ]

    assert '"api:${PROD_ACCEPTANCE_RAILWAY_API_SERVICE_ID}"' in provider
    assert '"worker:${PROD_ACCEPTANCE_RAILWAY_WORKER_SERVICE_ID}"' in provider
    assert '"scheduler:${PROD_ACCEPTANCE_RAILWAY_SCHEDULER_SERVICE_ID}"' in provider
    assert 'environment "$PROD_ACCEPTANCE_RAILWAY_ENVIRONMENT_ID"' in provider
    assert "serviceInstance(serviceId:" in provider
    assert "query deployment($id:" not in provider

    verifier = source[
        source.index("Verify independently observed deployment identities") :
        source.index("Setup Python backend")
    ]
    assert '--expected-frontend-project "$PROD_ACCEPTANCE_VERCEL_PROJECT_ID"' in verifier


def test_operator_deployment_ids_are_validated_before_provider_calls() -> None:
    source = _source()
    gate = source.index("Fail closed on operator intent and branch")
    providers = source.index("Observe production deployment identities from providers")
    window = source[gate:providers]

    assert "PROD_INPUT_BACKEND_DEPLOYMENT_ID" in window
    assert "PROD_INPUT_FRONTEND_DEPLOYMENT_ID" in window
    assert "RAILWAY_DEPLOYMENT_ID_RE" in window
    assert "VERCEL_DEPLOYMENT_ID_RE" in window
    assert "PROD_INPUT_BACKEND_DEPLOYMENT_ID" in window
    assert "PROD_INPUT_FRONTEND_DEPLOYMENT_ID" in window


def test_readonly_database_secret_is_not_passed_on_process_argv() -> None:
    source = _source()
    assert "--database-url" not in source
    assert (
        "PROD_ACCEPTANCE_DATABASE_URL_READONLY: "
        "${{ secrets.PROD_ACCEPTANCE_DATABASE_URL_READONLY }}"
    ) in source


def test_production_workflow_has_no_duplicate_step_names() -> None:
    source = _source()
    step_names = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            step_names.append(stripped.removeprefix("- name:").strip())

    duplicates = sorted({name for name in step_names if step_names.count(name) > 1})
    assert duplicates == [], f"duplicate production workflow steps: {duplicates}"


def test_health_poll_does_not_reload_analysis_dashboard() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    start = spec.index("async function loadHealth(")
    end = spec.index("async function createProject(", start)
    health_poll = spec[start:end]

    assert "page.goto(" not in health_poll
    assert "page.request.get(" in health_poll


def test_health_poll_reuses_observed_browser_auth_headers() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    start = spec.index("async function loadHealth(")
    end = spec.index("async function createProject(", start)
    health_poll = spec[start:end]

    assert "observedApiAuthContext" in spec
    assert 'headers: observedApiAuthContext.headers' in health_poll
    assert "Authorization:" in spec
    assert '"X-Tenant-ID"' in spec


def test_health_poll_is_bounded_and_ui_navigation_follows_convergence() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    assert "HEALTH_POLL_INTERVAL_MS = 10_000" in spec
    assert "HEALTH_POLL_MAX_REQUESTS = 6" in spec

    analyzed = spec.index('expect(terminal.lifecycle_status).toBe("analyzed");')
    wait_health = spec.index("const health = await waitForHealth(page, projectId);", analyzed)
    analysis_nav = spec.index(
        "observedApiAuthContext.origin}/projects/${projectId}/analysis",
        analyzed,
    )
    assert wait_health < analysis_nav


def test_health_poll_has_fail_closed_status_diagnostics() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    assert "PROD_ACCEPTANCE_HEALTH_AUTH_FAILED" in spec
    assert "PROD_ACCEPTANCE_HEALTH_REQUEST_ERROR" in spec
    start = spec.index("async function loadHealth(")
    end = spec.index("async function waitForHealth(", start)
    assert "cause:" not in spec[start:end]
    assert "Retry-After" in spec
    assert "last_status=" in spec
    assert "assessment_count=" in spec


def test_health_poll_uses_observed_canonical_browser_origin() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    assert "ObservedApiAuthContext" in spec
    assert "requireProductionOrigin(response.url())" in spec

    start = spec.index("async function loadHealth(")
    end = spec.index("async function waitForHealth(", start)
    health_loader = spec[start:end]

    assert "observedApiAuthContext.origin" in health_loader
    assert "headers: observedApiAuthContext.headers" in health_loader
    assert '${baseUrl()}/api/v1/projects/${projectId}/health' not in health_loader


def test_document_poll_does_not_reload_documents_dashboard() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    start = spec.index("async function loadDocument(")
    end = spec.index("async function waitForDocumentAttentionOrCompletion(", start)
    document_poll = spec[start:end]

    assert "page.goto(" not in document_poll
    assert "page.request.get(" in document_poll


def test_document_poll_is_bounded_to_six_requests_per_minute() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    assert "DOCUMENT_POLL_INTERVAL_MS = 10_000" in spec
    start = spec.index("async function pollDocumentUntilTerminal(")
    end = spec.index("async function waitForDocumentAttentionOrCompletion(", start)
    document_poll = spec[start:end]
    assert "PROCESSING_TIMEOUT_MS" in document_poll
    assert "Retry-After" in spec


def test_upload_captures_canonical_auth_context_for_direct_document_poll() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    upload = spec[
        spec.index("async function uploadFixture(") :
        spec.index("async function approveExactDocumentReview(")
    ]
    assert "captureObservedApiAuthContext(response)" in upload
    assert "requireProductionOrigin(response.url())" in spec


def test_production_journey_resets_observed_api_auth_context() -> None:
    spec = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "tests"
        / "e2e"
        / "prod-acceptance"
        / "706-production-synthetic.spec.ts"
    ).read_text(encoding="utf-8")

    journey = spec[
        spec.index('test("real user completes the canonical production journey"') :
    ]
    sign_in = journey.index("await signInSyntheticProductionUser(page);")
    reset = journey.index("observedApiAuthContext = null;")
    assert reset < sign_in
