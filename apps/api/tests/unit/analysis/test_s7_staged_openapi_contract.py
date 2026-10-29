"""ACC-01: a staged S7 OpenAPI update must not erase four-source S2 contracts."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
REVIEW_ROUTE = "/api/v1/projects/{project_id}/technical-wbs/reviews"
CANONICAL_ROUTE = "/api/v1/projects/{project_id}/technical-wbs/canonical-links"
S7_MODELS = {
    "TechnicalMappingDecision",
    "TechnicalWBSReviewHistoryEntry",
    "TechnicalWBSReviewRequest",
    "TechnicalWBSReviewResponse",
    "CanonicalTechnicalWBSLinkRequest",
    "CanonicalTechnicalWBSLinkResponse",
    "CurrentCanonicalTechnicalWBSLinkResponse",
}


def test_checked_in_json_and_yaml_keep_s2_and_add_audit_only_s7() -> None:
    json_doc = json.loads((ROOT / "apps/web/schema/api.json").read_text(encoding="utf-8"))
    yaml_doc = yaml.safe_load((ROOT / "docs/api/openapi.yaml").read_text(encoding="utf-8"))

    # The two checked-in formats must describe the same API paths and models.
    assert set(json_doc["paths"]) == set(yaml_doc["paths"])
    assert set(json_doc["components"]["schemas"]) == set(yaml_doc["components"]["schemas"])

    for document in (json_doc, yaml_doc):
        schemas = document["components"]["schemas"]
        assert "DocumentRevisionRef" in schemas, "S2 revision identity may not disappear"
        document_item = schemas["DocumentItem"]["properties"]
        assert {"trusted_revision", "pending_revision"} <= set(document_item)
        assert "blob_hash" in schemas["RevisionStatus"]["properties"]
        assert "DocumentEntityResponse" in schemas
        assert S7_MODELS <= set(schemas)
        assert set(document["paths"][REVIEW_ROUTE]) == {"get", "post"}
        assert set(document["paths"][CANONICAL_ROUTE]) == {"get", "post"}
        assert (
            document["paths"][CANONICAL_ROUTE]["post"]["requestBody"]["content"]
            ["application/json"]["schema"]["$ref"]
            == "#/components/schemas/CanonicalTechnicalWBSLinkRequest"
        )
        assert (
            document["paths"][CANONICAL_ROUTE]["get"]["responses"]["200"]["content"]
            ["application/json"]["schema"]["items"]["$ref"]
            == "#/components/schemas/CurrentCanonicalTechnicalWBSLinkResponse"
        )
        assert schemas["CanonicalTechnicalWBSLinkRequest"]["properties"]["approval"]["const"] == (
            "APPROVE_CANONICAL_LINK"
        )
        assert (
            schemas["CurrentCanonicalTechnicalWBSLinkResponse"]["properties"]["state"]["enum"]
            == ["CURRENT", "STALE_SOURCE", "STALE_WBS", "STALE_BOTH", "UNVERIFIED"]
        )

    exports = (ROOT / "apps/web/lib/api/generated/models/index.ts").read_text(
        encoding="utf-8"
    )
    assert 'export * from "./documentRevisionRef";' in exports
    for model in (
        "technicalMappingDecision",
        "technicalWBSReviewHistoryEntry",
        "technicalWBSReviewRequest",
        "technicalWBSReviewResponse",
    ):
        assert f'export * from "./{model}";' in exports
