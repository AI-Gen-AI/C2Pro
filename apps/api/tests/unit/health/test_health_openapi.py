"""TS-UD-HEALTH-018-006 - Generated OpenAPI includes project health endpoint."""

from __future__ import annotations

from pathlib import Path


def test_generated_openapi_contains_project_health_path() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    openapi = (repo_root / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")

    assert "/api/v1/projects/{project_id}/health:" in openapi
