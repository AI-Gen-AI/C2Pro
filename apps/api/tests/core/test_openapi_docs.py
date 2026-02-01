"""
OpenAPI & Docs Availability Tests

Refers to Suite ID: TS-UA-DTO-ALL-001.
"""

from __future__ import annotations

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
