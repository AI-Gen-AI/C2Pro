"""Sync gate for Health classifier provenance: API schema + generated TS client."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.health.domain.health_vector import HealthVector

ROOT = Path(__file__).resolve().parents[5]
KEY = "single_document_classification_method_version"
VERSIONS = {"router_no_prior_v1", "router_clause_anchors_v2"}


def test_version_provenance_matches_openapi_and_web_schema() -> None:
    model_prop = dict(HealthVector.model_json_schema()["properties"][KEY])
    # FastAPI strips Pydantic's default=None from the public OpenAPI surface.
    assert model_prop.pop("default", None) is None
    yaml_schema = yaml.safe_load((ROOT / "docs/api/openapi.yaml").read_text())
    json_schema = json.loads((ROOT / "apps/web/schema/api.json").read_text())
    yaml_prop = yaml_schema["components"]["schemas"]["HealthVector"]["properties"][KEY]
    json_prop = json_schema["components"]["schemas"]["HealthVector"]["properties"][KEY]
    assert model_prop == yaml_prop == json_prop
    assert set(yaml_prop["anyOf"][0]["enum"]) == VERSIONS
    assert {"type": "null"} in yaml_prop["anyOf"]


def test_orval_generated_client_exposes_optional_method_version() -> None:
    model = (ROOT / "apps/web/lib/api/generated/models/healthVector.ts").read_text()
    enum = (
        ROOT
        / "apps/web/lib/api/generated/models/healthVectorSingleDocumentClassificationMethodVersion.ts"
    ).read_text()
    assert f"{KEY}?: HealthVectorSingleDocumentClassificationMethodVersion" in model
    assert all(v in enum for v in VERSIONS)
