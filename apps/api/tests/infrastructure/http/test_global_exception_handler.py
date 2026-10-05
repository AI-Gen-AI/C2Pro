"""
Infrastructure & DTO Tests (TDD - RED Phase)

Refers to Suite IDs: TS-UA-DTO-ALL-001, TS-UAD-HTTP-ERR-001, TS-INT-EXT-LLM-002.
"""

from __future__ import annotations

from collections.abc import Iterable
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.core.exceptions import DomainValidationError
from src.core.handlers import register_exception_handlers


class TestGlobalExceptionHandler:
    """Refers to Suite ID: TS-UAD-HTTP-ERR-001."""

    def test_domain_validation_error_maps_to_422(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        def boom():
            raise DomainValidationError(message="Invalid payload")

        client = TestClient(app)
        response = client.get("/boom")

        assert response.status_code == 422
        body = response.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["status_code"] == 422
        assert body["message"] == "Invalid payload"
        assert "timestamp" in body
        assert body["path"] == "/boom"


class TestAllDtoSerialization:
    """Refers to Suite ID: TS-UA-DTO-ALL-001."""

    def test_all_dtos_roundtrip_json(self):
        from src.core.dto_registry import get_all_dtos

        dtos: Iterable[tuple[type[BaseModel], dict]] = get_all_dtos()

        for dto_cls, sample in dtos:
            instance = dto_cls.model_validate(sample)
            json_payload = instance.model_dump_json()
            restored = dto_cls.model_validate_json(json_payload)
            assert restored == instance
