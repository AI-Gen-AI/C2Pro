"""TS-CI-BACKEND-GUARDS-001

Regression checks for backend CI workflow prerequisites.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_unit_workflow_excludes_integration_marked_tests() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "ci.yml"
    contents = workflow.read_text(encoding="utf-8")

    assert '-m "not integration"' in contents
    assert "--cov-report=xml:coverage.xml" in contents
    assert "--cov-fail-under=0" in contents


def test_database_backed_ci_workflows_export_test_database_url() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    workflow_paths = [
        repo_root / ".github" / "workflows" / "ci.yml",
        repo_root / ".github" / "workflows" / "real-document-operability.yml",
    ]

    for workflow in workflow_paths:
        contents = workflow.read_text(encoding="utf-8")
        assert "DATABASE_URL: postgresql://postgres:postgres@localhost:5433/c2pro_test" in contents
        assert "TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5433/c2pro_test" in contents


def test_test_compose_uses_pgvector_image() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    compose_file = repo_root / "docker-compose.test.yml"
    contents = compose_file.read_text(encoding="utf-8")

    assert "pgvector/pgvector:pg15" in contents


def test_hitl_auth_script_does_not_embed_real_jwt() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "test_hitl_auth.py"
    contents = script.read_text(encoding="utf-8")

    assert "eyJhbGciOiJIUzI1Ni" not in contents


def test_openapi_schema_examples_do_not_use_jwt_like_placeholders() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    schema_paths = [
        repo_root / "apps" / "web" / "schema" / "api.json",
        repo_root / "docs" / "api" / "openapi.yaml",
    ]

    for schema in schema_paths:
        contents = schema.read_text(encoding="utf-8")
        assert '"access_token": "eyJ' not in contents
        assert '"refresh_token": "eyJ' not in contents
        assert "access_token: eyJ" not in contents
        assert "refresh_token: eyJ" not in contents


def test_qa_swarm_context_analyzer_uses_ast_parent_map() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    analyzer = repo_root / "scripts" / "agents" / "qa_swarm" / "context_analyzer_agent.py"
    contents = analyzer.read_text(encoding="utf-8")

    assert "ast.iter_child_nodes(parent)" in contents
    assert 'node in getattr(parent, "body", [])' not in contents


def test_frontend_e2e_workflows_export_clerk_test_keys() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    workflows = [
        repo_root / ".github" / "workflows" / "ci.yml",
    ]

    for workflow in workflows:
        contents = workflow.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:" in contents
        assert "CLERK_PUBLISHABLE_KEY:" in contents
        assert "CLERK_SECRET_KEY: ${{ secrets.CLERK_SECRET_KEY }}" in contents
        assert "CLERK_TESTING_TOKEN: ${{ secrets.CLERK_TESTING_TOKEN }}" in contents
        assert "Skipping Clerk-backed E2E smoke tests" in contents


def test_frontend_api_generation_check_formats_orval_output_before_diff() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    package_json = repo_root / "apps" / "web" / "package.json"
    contents = package_json.read_text(encoding="utf-8")

    assert '"generate:api:check"' in contents
    assert "pnpm exec prettier --write lib/api/generated schema/api.json" in contents
    assert "git diff --exit-code -- lib/api/generated schema/api.json" in contents


def test_real_document_operability_workflow_runs_required_quality_gates() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-012, TASK-OPS-DOCFLOW-013, TASK-OPS-DOCFLOW-014, TASK-OPS-DOCFLOW-015, TASK-OPS-DOCFLOW-016."""

    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "real-document-operability.yml"

    assert workflow.exists()
    contents = workflow.read_text(encoding="utf-8")

    assert "TASK-OPS-DOCFLOW-012" in contents
    assert "C2PRO_AI_MOCK: \"1\"" in contents
    assert "python -m pytest tests/integration/document_flow/ -q" in contents
    assert (
        "python -m pytest tests/unit/core/ai/ "
        "--cov=src/core/ai --cov-report=term-missing --cov-fail-under=70 -q"
    ) in contents
    assert "tests/unit/core/observability tests/unit/core/resilience tests/unit/core/security" in contents
    assert "--cov=src/core/observability --cov=src/core/resilience --cov=src/core/security" in contents
    assert "python -m pytest tests/ -x -q" in contents
    assert "python -m evals.run_evals" in contents
    assert "python -m pytest tests/evals/test_golden_corpus.py -q" in contents
    assert "pnpm lint" in contents
    assert "real-document-operability-blockers.md" in contents
    assert "TASK-COH-V2-VERSIONING-006" in contents
    assert "TASK-OPS-DOCFLOW-016" not in contents
    assert "src.alerts.router" not in contents
    assert "get_bom_repository" not in contents
    assert "TASK-OPS-DOCFLOW-015" not in contents
    assert "No module named 'schemathesis'" not in contents
    assert "Upload blocker tracking" in contents
    assert "TASK-OPS-DOCFLOW-014" not in contents
    assert "golden.evaluators" not in contents
    assert "TASK-OPS-DOCFLOW-013" not in contents
    assert "test_hitl_resume_metrics.py::test_checkpoint_load_errors_are_recorded" not in contents


def test_backend_requirements_include_schemathesis_contract_dependency() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-015."""

    repo_root = Path(__file__).resolve().parents[4]
    requirements = repo_root / "apps" / "api" / "requirements.txt"
    contents = requirements.read_text(encoding="utf-8")

    assert "schemathesis>=4.22.4" in contents
    assert "tenacity>=9.1.2,<10.0" in contents


def test_backend_requirements_include_langchain_anthropic_compatible_sdk() -> None:
    """Test Suite ID: TASK-BCK-078."""

    repo_root = Path(__file__).resolve().parents[4]
    requirements = repo_root / "apps" / "api" / "requirements.txt"
    contents = requirements.read_text(encoding="utf-8")

    assert "langchain-anthropic==1.4.8" in contents
    assert "anthropic>=0.78.0,<1.0.0" in contents
    assert "pydantic-settings>=2.10.1,<3.0.0" in contents
    assert "supabase==2.31.0" in contents
    assert "httpx>=0.28.1,<1.0.0" in contents
    assert "uvicorn[standard]>=0.51.0,<1.0.0" in contents
    assert "websockets>=13.0.0,<17.0" in contents
    assert "anthropic==0.18.1" not in contents
    assert "pydantic-settings==2.1.0" not in contents
    assert "supabase==2.5.0" not in contents
    assert "httpx==0.27.0" not in contents
    assert "httpx>=0.27.1,<1.0.0" not in contents
    assert "uvicorn[standard]==0.27.1" not in contents
    assert "websockets==12.0" not in contents


def test_production_contract_drift_repair_migration_restores_alerts_and_stakeholders_columns() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001, TASK-BCK-051."""

    repo_root = Path(__file__).resolve().parents[4]
    migration = (
        repo_root
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "20260516_0001_repair_alerts_stakeholders_contract_drift.py"
    )
    contents = migration.read_text(encoding="utf-8")

    assert "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS category" in contents
    assert "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS description" in contents
    assert "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS affected_entities" in contents
    assert "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS alert_metadata" in contents
    assert "ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS approval_status" in contents
    assert "ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS stakeholder_metadata" in contents
    assert "column_name = 'message'" in contents
    assert "UPDATE alerts SET description = COALESCE(description, message, '')" in contents
    assert "ELSE\n                UPDATE alerts SET description = COALESCE(description, '')" in contents
    assert "column_name = 'metadata'" in contents
    assert "SET stakeholder_metadata = COALESCE(stakeholder_metadata, metadata, '{}'::jsonb)" in contents
    assert "SET stakeholder_metadata = COALESCE(stakeholder_metadata, '{}'::jsonb)" in contents


def test_followup_alerts_drift_repair_adds_related_clause_ids_in_new_revision() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001, TASK-BCK-054."""

    repo_root = Path(__file__).resolve().parents[4]
    migration = (
        repo_root
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "20260516_0002_add_alerts_related_clause_ids.py"
    )
    contents = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20260516_0002"' in contents
    assert 'down_revision: str | None = "20260516_0001"' in contents
    assert "ALTER TABLE alerts" in contents
    assert "ADD COLUMN IF NOT EXISTS related_clause_ids UUID[]" in contents


def test_hotfix_migration_chain_has_no_duplicate_revisions() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001, TASK-BCK-056."""

    repo_root = Path(__file__).resolve().parents[4]
    versions_dir = repo_root / "apps" / "api" / "alembic" / "versions"
    revision_markers = [
        path.read_text(encoding="utf-8")
        for path in versions_dir.glob("20260516_000*.py")
    ]

    assert sum('revision: str = "20260516_0002"' in contents for contents in revision_markers) == 1
    assert sum('revision: str = "20260516_0003"' in contents for contents in revision_markers) == 1
    assert sum('revision: str = "20260516_0004"' in contents for contents in revision_markers) == 1


def test_document_type_drift_repair_normalizes_legacy_enum_name() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001, TASK-BCK-055."""

    repo_root = Path(__file__).resolve().parents[4]
    migration = (
        repo_root
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "20260516_0004_repair_document_type_enum_drift.py"
    )
    contents = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20260516_0004"' in contents
    assert 'down_revision: str | None = "20260516_0003"' in contents
    assert "typname = 'documenttype'" in contents
    assert "typname = 'document_type'" in contents
    assert "ALTER TABLE documents" in contents
    assert "ALTER COLUMN document_type TYPE document_type" in contents


def test_pnpm_action_setup_uses_package_manager_version() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    workflows = sorted((repo_root / ".github" / "workflows").glob("*.yml"))

    offenders = [
        workflow.relative_to(repo_root).as_posix()
        for workflow in workflows
        if _uses_explicit_pnpm_version(workflow.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def _uses_explicit_pnpm_version(contents: str) -> bool:
    """Detect forbidden pnpm version blocks without regex backtracking."""

    lines = [line.strip() for line in contents.splitlines()]
    for index in range(len(lines) - 2):
        if (
            lines[index].startswith("uses: pnpm/action-setup@")
            and lines[index + 1] == "with:"
            and lines[index + 2].startswith("version:")
        ):
            return True
    return False


def test_wireframe_coverage_installs_pnpm_before_node_cache_setup() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "wireframe-coverage.yml"
    contents = workflow.read_text(encoding="utf-8")

    assert contents.index("uses: pnpm/action-setup@") < contents.index("uses: actions/setup-node@")


def test_gitleaks_config_is_valid_toml() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    config = repo_root / ".gitleaks.toml"

    parsed = tomllib.loads(config.read_text(encoding="utf-8"))

    assert "allowlist" in parsed


def test_agent_swarm_dependencies_pin_langgraph_stack() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    requirements = repo_root / "scripts" / "agents" / "requirements.txt"
    contents = requirements.read_text(encoding="utf-8")

    assert "langgraph==1.1.9" in contents
    assert "langchain>=0.2.0,<0.4.0" not in contents


def test_code_auditor_skips_when_anthropic_secret_is_missing() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    agent = repo_root / "scripts" / "agents" / "code_auditor_agent.py"
    contents = agent.read_text(encoding="utf-8")

    assert 'os.environ.get("ANTHROPIC_API_KEY", "").strip()' in contents
    assert "ANTHROPIC_API_KEY is not configured" in contents


def test_alerts_impact_level_contract_has_idempotent_repair_migration() -> None:
    """Test Suite ID: TS-CI-BACKEND-GUARDS-001."""

    repo_root = Path(__file__).resolve().parents[4]
    migration = (
        repo_root
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "20260601_0001_repair_alerts_impact_level_drift.py"
    )

    contents = migration.read_text(encoding="utf-8")

    assert "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS impact_level" in contents
    assert 'revision: str = "20260601_0001"' in contents
    assert 'down_revision: str | None = "20260530_0001"' in contents


def test_backend_pytest_uses_importlib_mode_for_golden_package_isolation() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-014."""

    repo_root = Path(__file__).resolve().parents[4]
    pyproject = repo_root / "apps" / "api" / "pyproject.toml"
    contents = pyproject.read_text(encoding="utf-8")

    assert '"--import-mode=importlib"' in contents
