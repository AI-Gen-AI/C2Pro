"""TS-P0D-REPORT-003 - Generated OpenAPI includes the Current State Report endpoint."""

from __future__ import annotations

from pathlib import Path


def test_generated_openapi_contains_current_state_report_path() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    openapi = (repo_root / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")

    assert "/api/v1/projects/{project_id}/reports/current-state:" in openapi
    assert "CurrentStateReport:" in openapi
