from __future__ import annotations

import asyncio

import pytest

from src.core.exceptions import AIServiceError
from src.modules.ai.service import AIService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _DummyResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.model_used = "claude-test"
        self.input_tokens = 10
        self.output_tokens = 5
        self.latency_ms = 12.34


def _build_service() -> AIService:
    return AIService(
        anthropic_api_key="test-key",
        tenant_id=None,
        budget_remaining_usd=None,
        wrapper=object(),
    )


def test_parse_json_response_with_chatter() -> None:
    service = _build_service()
    raw = "Aqui tienes tu respuesta:\n{\"ok\": true, \"items\": [1, 2, 3]}"

    parsed = service._parse_json_response(raw)

    assert parsed["ok"] is True
    assert parsed["items"] == [1, 2, 3]


def test_extract_json_block_prefers_first_valid() -> None:
    service = _build_service()
    raw = "texto previo {\"a\": 1} y luego [\"ignored\"]"

    block = service._extract_json_block(raw)

    assert block == "{\"a\": 1}"


@pytest.mark.anyio
async def test_run_extraction_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()

    async def _fake_call_wrapper(system_prompt: str, user_content: str) -> _DummyResponse:
        return _DummyResponse("Resultado:\n[{\"name\": \"A\"}]")

    monkeypatch.setattr(service, "_call_wrapper", _fake_call_wrapper)

    result = await service.run_extraction("sys", "user")

    assert isinstance(result, list)
    assert result[0]["name"] == "A"


def test_parse_json_response_raises_ai_service_error() -> None:
    service = _build_service()
    with pytest.raises(AIServiceError):
        service._parse_json_response("no json here")
