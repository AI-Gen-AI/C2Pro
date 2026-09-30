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
