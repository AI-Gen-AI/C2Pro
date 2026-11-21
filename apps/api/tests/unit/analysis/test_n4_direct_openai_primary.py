from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

import pytest

from src.analysis.adapters.ai import n4_direct_openai_window_provider as p
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.llm_client import LLMResponse


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("C2PRO_N4_DIRECT_OPENAI_ROUTE", json.dumps({
        "provider": "openai",
        "model": "gpt-4.1",
        "context_tokens": 1000000,
        "output_tokens": 32768,
        "input_usd_m": "2",
        "output_usd_m": "8",
    }))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key-for-no-network-tests")
    return p.DirectOpenAIN4WindowProvider(
        max_output_tokens=2048, reservation_usd=Decimal("1.0"),
    )


@pytest.mark.asyncio
async def test_openai_direct_called_once_with_existing_uuid_and_source(setup, monkeypatch):
    calls = []
    async def fake_invoke(route, request, *, key, client):
        calls.append((route,request))
        return LLMResponse(
            content=json.dumps({"window_examined":True,"findings":[],"outstanding_references":[]}),
            model=route.model,input_tokens=345,output_tokens=44,
            cost_usd=0.00104,request_id=request.request_id,execution_time_ms=100,retries=0,
        )
    monkeypatch.setattr(p, "_invoke", fake_invoke)
    window = plan_n4_source_windows("Clause 9.6. Delivery delay notice rules."*20,revision_id=str(uuid4()))[0]
    req_id=str(uuid4())
    out=await setup.generate(window=window,tenant_id=uuid4(),request_id=req_id)
    assert len(calls)==1
    assert calls[0][1].request_id==req_id
    assert calls[0][1].max_tokens==2048
    assert calls[0][1].messages[0]["content"].find("Clause 9.6") > 0
    assert out.model_used=="gpt-4.1"
    assert out.input_tokens==345 and out.output_tokens==44
    assert out.provider_request_id==req_id


@pytest.mark.asyncio
async def test_openai_direct_denies_unreserved_oversize_no_network(monkeypatch):
    monkeypatch.setenv("C2PRO_N4_DIRECT_OPENAI_ROUTE", json.dumps({
        "provider":"openai","model":"gpt-4.1","context_tokens":1000000,
        "output_tokens":32768,"input_usd_m":"2","output_usd_m":"8",
    }))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key-for-no-network-tests")
    provider=p.DirectOpenAIN4WindowProvider(max_output_tokens=2048,reservation_usd=Decimal("0.000001"))
    window=plan_n4_source_windows("Clause 13. Notice due within 5 days.",revision_id=str(uuid4()))[0]
    with pytest.raises(p.FallbackUnavailable,match="Worst-case cost"):
        await provider.generate(window=window,tenant_id=uuid4(),request_id=str(uuid4()))


def test_openai_direct_unapproved_route_denied(monkeypatch):
    monkeypatch.setenv("C2PRO_N4_DIRECT_OPENAI_ROUTE", json.dumps({
        "provider":"gemini","model":"gemini-test","context_tokens":100000,
        "output_tokens":4000,"input_usd_m":"2","output_usd_m":"8",
    }))
    with pytest.raises(p.FallbackUnavailable,match="must be OpenAI"):
        p.DirectOpenAIN4WindowProvider(max_output_tokens=2048,reservation_usd=Decimal("1"))
