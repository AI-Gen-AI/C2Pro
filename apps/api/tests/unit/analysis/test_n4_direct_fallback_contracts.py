"""N4 provider switch is authorized only after a committed per-window escrow.

No model calls: validation relies on HTTP stubs and a fake already-N2-safe window.
"""
from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import anthropic
import httpx
import pytest

from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.direct_provider_fallback import (
    DirectRoute,
    FallbackUnavailable,
    fallback_after_unbilled_rejection,
)
from src.core.ai.llm_client import LLMRequest
from src.core.ai.model_router import ModelTier


class FakeWrapper:
    def __init__(self):
        self.llm_client = SimpleNamespace(max_retries=0)
        self.enable_cache = False
        self.cache_service = None
        self.model_router = SimpleNamespace(
            configs={ModelTier.STANDARD: SimpleNamespace(name="claude-sonnet-4-6")}
        )
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            content='{"window_examined":true,"findings":[],"outstanding_references":[]}',
            model_used="gpt-4.1", cost_usd=0.012,
            input_tokens=100, output_tokens=25,
        )


def route(provider="openai"):
    return DirectRoute(
        provider=provider, model="gpt-4.1", context_tokens=200000,
        output_tokens=32000, input_usd_m=Decimal("2"),
        output_usd_m=Decimal("8"),
    )


@pytest.mark.asyncio
async def test_n4_provider_preserves_original_sha_and_committed_escrow(monkeypatch):
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ROUTES", json.dumps([{
        "provider": "openai", "model": "gpt-4.1",
        "context_tokens": 200000, "output_tokens": 32000,
        "input_usd_m": 2, "output_usd_m": 8,
    }]))
    wrapper = FakeWrapper()
    adapter = AnthropicN4WindowProvider(
        wrapper=wrapper, fallback_reservation_usd=Decimal("0.25")
    )
    window = plan_n4_source_windows(
        "Clause 9.6 contractor shall notify purchaser.",
        revision_id=str(uuid4()),
    )[0]
    receipt = await adapter.generate(
        window=window, tenant_id=uuid4(), request_id=str(uuid4()),
    )
    assert adapter.model_name == "claude-sonnet-4-6"
    assert adapter.approved_fallback_models == frozenset({"gpt-4.1"})
    assert receipt.model_used == "gpt-4.1"
    assert receipt.reported_cost_usd == "0.012"
    request = wrapper.requests[0]
    assert request.metadata["n4_incremental_window"] is True
    assert request.metadata["n4_reservation_committed"] is True
    assert request.metadata["n4_reserved_usd"] == "0.25"
    assert window.context_text in request.prompt
    assert request.bypass_anonymization is True


@pytest.mark.asyncio
async def test_n4_direct_fallback_uses_reserved_uuid_without_second_invoice(monkeypatch):
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    network_calls = []
    def handler(req: httpx.Request):
        network_calls.append(req.url.host)
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {
                "content": '{"window_examined":true,"findings":[],"outstanding_references":[]}'
            }}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 50},
        })
    req = LLMRequest(
        model="claude-sonnet-4-6",
        system="Risk JSON",
        messages=[{"role": "user", "content": "Clause 5.1 warranty."}],
        max_tokens=1024,
        tenant_id=uuid4(),
        request_id=str(uuid4()),
        metadata={"n4_incremental_window": True,
                  "n4_reservation_committed": True,
                  "n4_reserved_usd": "0.25"},
    )
    anthropic_req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(
        400, request=anthropic_req,
        json={"error": {"message": "Your credit balance is too low"}}
    )
    error = anthropic.BadRequestError(
        "rejected", response=response, body=None
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        actual = await fallback_after_unbilled_rejection(
            req, error, routes=[route()], key_lookup=lambda _: "x" * 24,
            client=client,
        )
    assert actual.model == "gpt-4.1"
    assert actual.input_tokens == 150
    assert actual.output_tokens == 50
    assert actual.cost_usd > 0
    assert network_calls == ["api.openai.com"]


@pytest.mark.asyncio
async def test_n4_rejects_fabricated_reservation_id(monkeypatch):
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "Clause 5"}],
        tenant_id=uuid4(),
        request_id="unverified-run",
        metadata={"n4_incremental_window": True,
                  "n4_reservation_committed": True,
                  "n4_reserved_usd": "0.25"},
    )
    primary_req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.BadRequestError(
        "no credit",
        response=httpx.Response(
            400, request=primary_req,
            json={"error": {"message": "credit balance too low"}}
        ),
        body=None,
    )
    with pytest.raises(FallbackUnavailable, match="UUID"):
        await fallback_after_unbilled_rejection(
            req, err, routes=[route()],
            key_lookup=lambda _: "x" * 24,
        )


def test_migration_mirror_is_exact_and_additive():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    path = root / "alembic/versions/20261118_0001_n4_actual_provider_provenance.py"
    spec = importlib.util.spec_from_file_location("n4_actual_model_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (root.parent.parent / "supabase/migrations" / module.SUPABASE_MIRROR).read_text() == module.supabase_sql()
    assert all("ALTER TABLE" in x for x in module.UPGRADE_STATEMENTS)
