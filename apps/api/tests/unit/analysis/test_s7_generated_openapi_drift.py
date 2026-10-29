"""S7 canonical-links OpenAPI is generated from the live FastAPI router, not patched by hand."""

from pathlib import Path

import yaml

from src.main import create_application

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_checked_in_openapi_yaml_matches_live_fastapi_generator() -> None:
    generated = yaml.safe_dump(
        create_application().openapi(),
        sort_keys=False,
        allow_unicode=False,
    )
    checked_in = (REPO_ROOT / "docs/api/openapi.yaml").read_text(encoding="utf-8")
    assert checked_in == generated, (
        "OpenAPI drift: regenerate from FastAPI; do not discard existing S2 schema models"
    )
