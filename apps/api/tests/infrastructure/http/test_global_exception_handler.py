"""
Infrastructure & DTO Tests (TDD - RED Phase)

Refers to Suite IDs: TS-UA-DTO-ALL-001, TS-UAD-HTTP-ERR-001, TS-INT-EXT-LLM-002.
"""

from __future__ import annotations

from typing import Iterable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from unittest.mock import AsyncMock

from src.core.handlers import register_exception_handlers
from src.core.exceptions import DomainValidationError


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


class TestLlmFallback:
    """Refers to Suite ID: TS-INT-EXT-LLM-002."""

    @pytest.mark.asyncio
    async def test_fallback_to_openai_when_anthropic_fails(self):
        from src.core.ai.fallback_client import LLMFallbackClient

        anthropic_client = AsyncMock()
        openai_client = AsyncMock()
        anthropic_client.generate.side_effect = RuntimeError("Anthropic down")
        openai_client.generate.return_value = {"content": "ok"}

        client = LLMFallbackClient(
            primary_client=anthropic_client,
            fallback_client=openai_client,
        )

        result = await client.generate(prompt="hello")

        anthropic_client.generate.assert_awaited_once()
        openai_client.generate.assert_awaited_once()
        assert result == {"content": "ok"}
