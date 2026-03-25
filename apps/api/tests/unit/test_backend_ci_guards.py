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
