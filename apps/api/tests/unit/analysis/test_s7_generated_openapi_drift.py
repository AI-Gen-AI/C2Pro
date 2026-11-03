"""The checked-in S7 contracts match FastAPI without relying on unrelated schema versions."""

from pathlib import Path

import yaml

from src.main import create_application

REPO_ROOT = Path(__file__).resolve().parents[5]
PATHS = (
    "/api/v1/projects/{project_id}/technical-wbs/reviews",
    "/api/v1/projects/{project_id}/technical-wbs/canonical-links",
)
MODELS = (
    "TechnicalMappingDecision",
    "TechnicalWBSReviewHistoryEntry",
    "TechnicalWBSReviewRequest",
    "TechnicalWBSReviewResponse",
    "CanonicalTechnicalWBSLinkRequest",
    "CanonicalTechnicalWBSLinkResponse",
    "CurrentCanonicalTechnicalWBSLinkResponse",
)


def test_s7_openapi_matches_live_fastapi_routes_and_models() -> None:
    generated = create_application().openapi()
    checked_in = yaml.safe_load(
        (REPO_ROOT / "docs/api/openapi.yaml").read_text(encoding="utf-8")
    )

    for path in PATHS:
        assert checked_in["paths"][path] == generated["paths"][path]
    for model in MODELS:
        assert checked_in["components"]["schemas"][model] == generated["components"]["schemas"][model]
