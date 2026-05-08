"""TS-CI-BACKEND-GUARDS-001

Regression checks for backend CI workflow prerequisites.
"""

from __future__ import annotations

from pathlib import Path


def test_unit_workflow_excludes_integration_marked_tests() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow = repo_root / ".github" / "workflows" / "tests.yml"
    contents = workflow.read_text(encoding="utf-8")

    assert '-m "not integration"' in contents


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
    schema = repo_root / "apps" / "web" / "schema" / "api.json"
    contents = schema.read_text(encoding="utf-8")

    assert '"access_token": "eyJ' not in contents
    assert '"refresh_token": "eyJ' not in contents


def test_real_document_operability_workflow_runs_required_quality_gates() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-012, TASK-OPS-DOCFLOW-013, TASK-OPS-DOCFLOW-014."""

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
    assert "TASK-OPS-DOCFLOW-015" in contents
    assert "TASK-OPS-DOCFLOW-016" in contents
    assert "TASK-OPS-DOCFLOW-014" not in contents
    assert "golden.evaluators" not in contents
    assert "TASK-OPS-DOCFLOW-013" not in contents
    assert "test_hitl_resume_metrics.py::test_checkpoint_load_errors_are_recorded" not in contents


def test_backend_pytest_uses_importlib_mode_for_golden_package_isolation() -> None:
    """Test Suite ID: TASK-OPS-DOCFLOW-014."""

    repo_root = Path(__file__).resolve().parents[4]
    pyproject = repo_root / "apps" / "api" / "pyproject.toml"
    contents = pyproject.read_text(encoding="utf-8")

    assert '"--import-mode=importlib"' in contents
