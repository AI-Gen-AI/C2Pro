"""Static safety contracts for the #867/#686 production qualification workflows."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
P0C = REPO_ROOT / ".github" / "workflows" / "prod-p0c-qualification.yml"
B1 = REPO_ROOT / ".github" / "workflows" / "prod-b1-12-qualification.yml"
PLAYWRIGHT = REPO_ROOT / "apps" / "web" / "playwright.config.ts"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_blocks(source: str) -> list[str]:
    lines = source.splitlines()
    blocks: list[str] = []
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
            blocks.append(inline)
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
        blocks.append("\n".join(block))
    return blocks


def test_followup_workflows_are_manual_only_and_protected() -> None:
    for path, confirmation in ((P0C, "RUN-ISSUE-686"), (B1, "RUN-ISSUE-867")):
        source = _source(path)
        assert "workflow_dispatch:" in source
        assert "schedule:" not in source
        assert "pull_request:" not in source
        assert "push:" not in source
        assert "environment: production-qualification" in source
        assert confirmation in source
        assert 'test "$GITHUB_REF_NAME" = "main"' in source
        assert 'test "$STAGED_CLEAR" = "true"' in source


def test_followup_workflows_observe_providers_before_product_mutation() -> None:
    for path, browser_step in (
        (P0C, "Execute P0c real production browser journey"),
        (B1, "Execute B1-12 real production browser journey"),
    ):
        source = _source(path)
        railway = source.index("Observe Railway production identities")
        vercel = source.index("Observe Vercel production identity")
        verify = source.index("Verify independently observed deployment identities")
        browser = source.index(browser_step)
        assert railway < verify < browser
        assert vercel < verify < browser
        assert "verify_prod_deployment_identity.py" in source
        assert "deployment-identity.json" in source


def test_followup_workflows_do_not_self_assert_observed_shas() -> None:
    for path in (P0C, B1):
        source = _source(path)
        assert "backend_sha=\"$(python -c" in source
        assert "frontend_sha=\"$(python -c" in source
        assert "PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA=$BACKEND_SHA" not in source
        assert "PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA=$FRONTEND_SHA" not in source


def test_dispatch_inputs_are_not_interpolated_directly_into_shell() -> None:
    for path in (P0C, B1):
        blocks = _run_blocks(_source(path))
        assert blocks
        assert all("${{ inputs." not in block for block in blocks)


def test_followup_workflows_keep_readonly_database_secret_off_argv() -> None:
    for path in (P0C, B1):
        source = _source(path)
        assert "--database-url" not in source
        assert (
            "PROD_ACCEPTANCE_DATABASE_URL_READONLY: "
            "${{ secrets.PROD_ACCEPTANCE_DATABASE_URL_READONLY }}"
        ) in source


def test_p0c_contract_binds_real_journey_verifier_and_canonical_validator() -> None:
    source = _source(P0C)
    assert "686-production-what-changed.spec.ts" in source
    assert "verify_p0c_prod_journey.py" in source
    assert "build_p0c_prod_qualification_bundle.py" in source
    assert "validate_qualification_evidence.py" in source
    assert "RUN-ISSUE-706" not in source


def test_b1_contract_binds_real_review_rescore_and_independent_validator() -> None:
    source = _source(B1)
    assert "867-production-alerts-coherence.spec.ts" in source
    assert "generate_b1_prod_qualification_fixtures.py" in source
    assert "verify_b1_12_prod_acceptance.py" in source
    assert "build_b1_12_prod_qualification_bundle.py" in source
    assert "validate_b1_12_prod_qualification.py" in source
    assert "RUN-ISSUE-706" not in source


def test_followup_production_playwright_projects_disable_sensitive_artifacts() -> None:
    config = _source(PLAYWRIGHT)
    for project in ("prod-p0c", "prod-b1-12"):
        start = config.index(f'name: "{project}"')
        snippet = config[start : start + 900]
        assert 'trace: "off"' in snippet
        assert 'screenshot: "off"' in snippet
        assert 'video: "off"' in snippet
        assert "recordHar" not in snippet


def test_raw_provider_payloads_are_not_uploaded() -> None:
    for path in (P0C, B1):
        source = _source(path)
        upload = source[source.index("Upload bounded") :]
        assert "runtime/provider/" not in upload
        assert "runtime/deployment-identity.json" in upload
