"""
OpenAPI & Docs Availability Tests

Refers to Suite ID: TS-UA-DTO-ALL-001.
"""

from __future__ import annotations

import warnings

from fastapi.testclient import TestClient

from src.config import settings
from src.main import create_application


class TestOpenApiDocs:
    """Refers to Suite ID: TS-UA-DTO-ALL-001."""

    def test_docs_and_redoc_are_available(self):
        app = create_application()
        client = TestClient(app)

        docs = client.get("/docs")
        redoc = client.get("/redoc")

        assert docs.status_code == 200
        assert redoc.status_code == 200

    def test_openapi_json_is_available(self):
        app = create_application()
        client = TestClient(app)

        openapi = client.get(f"{settings.api_v1_prefix}/openapi.json")

        assert openapi.status_code == 200

    def test_openapi_operation_ids_are_unique_and_health_paths_are_preserved(self):
        """TS-OPS-HLT-WRK-001: health aliases must not collide in OpenAPI."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            schema = create_application().openapi()

        duplicate_operation_warnings = [
            str(warning.message)
            for warning in caught_warnings
            if "Duplicate Operation ID" in str(warning.message)
        ]
        operation_ids = [
            operation["operationId"]
            for path_item in schema["paths"].values()
            for operation in path_item.values()
            if isinstance(operation, dict) and "operationId" in operation
        ]

        assert not duplicate_operation_warnings
        assert len(operation_ids) == len(set(operation_ids))
        assert "/health/worker" in schema["paths"]
        assert "/api/v1/health/worker" in schema["paths"]
