"""Verify the real bridge/provider/wrapper chain with a non-network client."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.graph import n4_governed_bridge as bridge
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai import anthropic_wrapper as wrapper_module
from src.core.ai.model_router import ModelTier


class _MockTransportStop(BaseException):
    """Stop at the transport boundary without invoking fallback or settlement."""


@pytest.fixture
def seam(monkeypatch):
    source = "Clause 1: The contractor shall provide a warranty of 24 months."
    revision, tenant = uuid4(), uuid4()
    authority = SimpleNamespace(revision_id=revision, tenant_id=tenant)
    calls = []
    created = []
    model = SimpleNamespace(
        name="claude-sonnet-4-6", tier=ModelTier.STANDARD, max_tokens=8192,
        cost_per_1m_input=3.0, cost_per_1m_output=15.0,
    )

    class MockClient:
        def __init__(self, *, api_key, max_retries, timeout_seconds):
            assert api_key == "synthetic-unit-key"
            self.max_retries = max_retries
            self.timeout_seconds = timeout_seconds
            created.append(self)

        async def generate(self, request):
            calls.append(request)
            raise _MockTransportStop

    monkeypatch.setattr(wrapper_module.settings, "anthropic_api_key", "synthetic-unit-key")
    monkeypatch.setattr(wrapper_module, "LLMClient", MockClient)
    monkeypatch.setattr(wrapper_module, "PiiAnonymizerService", lambda: object())
    monkeypatch.setattr(wrapper_module, "get_model_router", lambda: SimpleNamespace(
        configs={ModelTier.STANDARD: model},
        select_model_with_budget_mode=lambda **_: model,
    ))
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setenv("C2PRO_N4_GRAPH_PRIMARY_PROVIDER", "anthropic")
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "0")
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setenv("C2PRO_N4_GRAPH_RUN_USD", "1")
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_USD", "1")
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_CHARS", "1000")
    monkeypatch.setenv("C2PRO_N4_GRAPH_OVERLAP_CHARS", "50")
    monkeypatch.setattr(bridge, "_identity", lambda _: (authority, uuid4(), source))
    monkeypatch.setattr(bridge, "_uat_inherited_scopes", lambda _: False)
    monkeypatch.setattr(bridge, "get_session_factory", lambda: object())
    return source, authority, created, calls


@pytest.mark.asyncio
@pytest.mark.parametrize(("attempt", "cap"), [(1, 8192), (2, 16384)])
async def test_effective_a5_bridge_request(monkeypatch, seam, attempt, cap):
    source, authority, created, calls = seam
    reservation = uuid4()

    class MockRunner:
        def __init__(self, *, provider, run_cap_usd, per_window_reservation_usd, **kwargs):
            assert run_cap_usd == per_window_reservation_usd == Decimal("1")
            assert provider.fallback_reservation_usd is None
            assert not provider.wrapper.enable_cache
            assert not provider.wrapper.enable_retry
            self.provider = provider

        async def run(self, **kwargs):
            window = plan_n4_source_windows(
                source, revision_id=str(authority.revision_id),
                max_context_chars=1000, overlap_chars=50,
            )[0]
            return await self.provider.generate_reserved(
                window=window, tenant_id=authority.tenant_id,
                request_id=str(reservation), attempt=attempt,
                reservation_usd=self.provider.reservation_for_attempt(
                    window, attempt=attempt, ceiling=Decimal("1"),
                ),
            )

    monkeypatch.setattr(bridge, "N4IncrementalRunner", MockRunner)
    with pytest.raises(_MockTransportStop):
        await bridge.run_governed_n4_in_graph({})
    assert len(created) == len(calls) == 1
    assert created[0].timeout_seconds == 300
    assert created[0].max_retries == 0
    req = calls[0]
    assert req.max_tokens == cap
    assert req.request_id == str(reservation)
    assert req.model == "claude-sonnet-4-6"
    assert req.tool_choice == {"type": "tool", "name": "record_window_findings"}
    assert req.metadata["prompt_version"] == "n4-compact-window-v2"
    assert req.bypass_cache
    assert "n4_reserved_usd" not in req.metadata


@pytest.mark.asyncio
async def test_insufficient_escrow_fails_before_runner_or_transport(monkeypatch, seam):
    _, _, created, calls = seam
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_USD", "0.01")

    def forbidden(*args, **kwargs):
        pytest.fail("must not allocate runner or DB before escrow preflight")

    monkeypatch.setattr(bridge, "N4IncrementalRunner", forbidden)
    monkeypatch.setattr(bridge, "get_session_factory", forbidden)
    with pytest.raises(ValueError, match="worst-case charge exceeds"):
        await bridge.run_governed_n4_in_graph({})
    assert len(created) == 1 and calls == []
