"""Legacy graph AIService cost-controller tests.

Test Suite ID: TS-QA-SWAGGER-ANALYSIS-002
"""

from __future__ import annotations

from typing import Any

import pytest


class _AsyncContext:
    def __init__(self, value: Any = object()) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakeCostController:
    checks: list[tuple[object, float]] = []
    tracks: list[tuple[object, float]] = []

    def __init__(self, db: object) -> None:
        self.db = db

    async def check_budget_availability(self, tenant_id: object, cost: float) -> None:
        self.checks.append((tenant_id, cost))

    def calculate_cost(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        _ = model, input_tokens, output_tokens
        return 0.02

    async def track_usage(self, tenant_id: object, cost: float) -> None:
        self.tracks.append((tenant_id, cost))


class _FakeWrapperResponse:
    content = '{"status": "OK", "notes": ""}'
    model_used = "claude-test"
    input_tokens = 12
    output_tokens = 8
    latency_ms = 3.0


class _FakeWrapper:
    async def generate(self, request: object) -> _FakeWrapperResponse:
        _ = request
        return _FakeWrapperResponse()


@pytest.mark.asyncio
async def test_ai_service_without_constructor_db_uses_tenant_session_cost_controller(
    monkeypatch,
) -> None:
    """Test Suite ID: TS-QA-SWAGGER-ANALYSIS-002."""
    from src.analysis.adapters.ai import anthropic_client

    _FakeCostController.checks = []
    _FakeCostController.tracks = []
    monkeypatch.delenv("C2PRO_TEST_LIGHT", raising=False)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(
        anthropic_client,
        "_get_cost_controller",
        lambda: (_FakeCostController, RuntimeError),
    )
    monkeypatch.setattr(
        anthropic_client,
        "get_session_with_tenant",
        lambda tenant_id: _AsyncContext(value={"tenant_id": tenant_id}),
    )

    service = anthropic_client.AIService(
        wrapper=_FakeWrapper(),
        tenant_id="00000000-0000-0000-0000-000000000099",
        db=None,
    )

    result = await service.run_extraction("critique system", "critique payload")

    assert result == {"status": "OK", "notes": ""}
    assert len(_FakeCostController.checks) == 1
    assert len(_FakeCostController.tracks) == 1
