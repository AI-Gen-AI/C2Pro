"""Real isolated PostgreSQL escrow for Coherence; provider replies are stubs.

Verifies reserve-before-network, settled billing for valid negative/positive
model responses, UNKNOWN on failures, replay refusal and per-tenant caps.
Does not certify a production provider, semantic results, or source attestation.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.coherence.adapters.ai.coherence_governed_wrapper import CoherenceCallIdentity
from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
from src.coherence.models import Clause
from src.core.ai.budget_escrow_audit import audit_tenant_escrow
from tests.integration.analysis.test_legacy_ai_service_escrow_pg import _patch_sessions
from tests.integration.analysis.test_legacy_shared_reservations_pg import _seed

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires isolated migrated *_test database"),
]


class StubProvider:
    enable_cache = False
    cache_service = None
    llm_client = SimpleNamespace(max_retries=0)

    def __init__(self, mode="negative"):
        self.mode = mode
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.mode == "error":
            raise TimeoutError("synthetic network uncertainty")
        cost = {
            "unknown": None, "zero": 0.0, "over_cap": 0.48,
        }.get(self.mode, 0.12)
        if self.mode == "malformed":
            content = '{"impact_score":'
        else:
            impact = 0.81 if self.mode == "positive" else 0
            content = json.dumps({
                "impact_score": impact,
                "confidence": 0.95,
                "rule_violated": bool(impact),
                "evidence": {
                    "quote": "Services will be available under written approval.",
                    "explanation": "Synthetic finding for transport testing",
                },
                "recommendation": "Review contract source",
            })
        return SimpleNamespace(
            content=content, cost_usd=cost,
            input_tokens=100, output_tokens=55,
            model_used="test-only-no-real-provider",
            latency_ms=2.0, cached=False, continuations=0,
        )


class CacheMiss:
    async def get(self, _key):
        raise AssertionError("governed Coherence must not read shared cache")

    async def set(self, _key, _value):
        raise AssertionError("governed Coherence must not write shared cache")


class AnalyticsStub:
    def __init__(self):
        self.records = []
    def record_usage(self, **kwargs):
        self.records.append(kwargs)


def _identity(authority, project):
    return CoherenceCallIdentity(
        tenant_id=authority.tenant_id, project_id=project,
        document_id=authority.document_id,
        revision_id=authority.revision_id, run_id=uuid4(),
        source_sha256="b" * 64,
    )


def _gate(identity, provider):
    gate = CoherenceLlmGate(
        governed_context=identity, governed_provider_wrapper=provider,
    )
    gate._cache = CacheMiss()
    gate._usage = AnalyticsStub()
    return gate


def _clause():
    return Clause(
        id="C-1",
        text="Services will be available under written approval.",
        data={},
    )


async def _ledger(authority):
    conn = await asyncpg.connect(_DSN)
    try:
        rows = await conn.fetch("""
            SELECT idempotency_key,call_source,status,reserved_usd,
                   billed_usd,input_tokens,output_tokens,provider_model
              FROM public.legacy_ai_usage_reservations
             WHERE tenant_id=$1 ORDER BY created_at
        """, authority.tenant_id)
        budget = await conn.fetchrow("""
            SELECT ai_spend_current, ai_spend_reserved_usd
              FROM public.tenants WHERE id=$1
        """, authority.tenant_id)
        return rows, budget
    finally:
        await conn.close()


def _flags(monkeypatch):
    monkeypatch.setenv("C2PRO_COHERENCE_ESCROW", "1")
    monkeypatch.setenv("C2PRO_COHERENCE_RESERVE_USD", "0.30")
    monkeypatch.setenv("C2PRO_COHERENCE_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")


@pytest.mark.parametrize("mode,success,status", [
    ("negative", True, "SETTLED"),
    ("positive", True, "SETTLED"),
    ("error", False, "UNKNOWN"),
    ("unknown", False, "UNKNOWN"),
    ("zero", False, "UNKNOWN"),
    ("over_cap", False, "SETTLED"),
    ("malformed", False, "SETTLED"),
])
async def test_coherence_escrow_real_postgres_before_call_and_replay(
    monkeypatch, mode, success, status,
):
    authority, project = await _seed(budget=1.0)
    engine = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
    )
    _patch_sessions(monkeypatch, engine)
    _flags(monkeypatch)
    provider = StubProvider(mode=mode)
    gate = _gate(_identity(authority, project), provider)
    tenant = str(authority.tenant_id)
    try:
        if success:
            result = await gate.evaluate_rule(
                tenant, "R-SCOPE-CLARITY-01", _clause(),
            )
            assert result.state == "evaluated"
            assert result.cost_charged_usd == pytest.approx(0.12)
            assert (result.finding is not None) == (mode == "positive")
        else:
            with pytest.raises(RuntimeError, match="usage unverified"):
                await gate.evaluate_rule(
                    tenant, "R-SCOPE-CLARITY-01", _clause(),
                )
        assert len(provider.requests) == 1
        assert provider.requests[0].use_cache is False
        assert provider.requests[0].max_tokens == 2048
        assert provider.requests[0].metadata["max_provider_segments"] == 1
        assert provider.requests[0].tenant_id == authority.tenant_id
        rows, balances = await _ledger(authority)
        assert len(rows) == 1
        assert rows[0]["call_source"] == "COHERENCE_RULE"
        assert rows[0]["status"] == status
        if status == "SETTLED":
            expected = Decimal("0.48") if mode == "over_cap" else Decimal("0.12")
            assert Decimal(rows[0]["billed_usd"]) == expected
            assert rows[0]["input_tokens"] == 100
            assert rows[0]["output_tokens"] == 55
            assert balances["ai_spend_current"] == pytest.approx(float(expected))
            assert balances["ai_spend_reserved_usd"] == 0
        if mode == "over_cap":
            async with AsyncSession(engine) as session, session.begin():
                await session.execute(
                    text("SELECT set_config('app.current_tenant', :tenant, true)"),
                    {"tenant": tenant},
                )
                report = await audit_tenant_escrow(
                    session, tenant_id=authority.tenant_id,
                )
                assert report.financial_reconciliation_passed
                assert "PROVIDER_CHARGE_EXCEEDED_RESERVATION" in report.findings
                assert report.legacy.settled_overage_count == 1
                assert report.legacy.settled_overage_usd == Decimal("0.18")
        if status != "SETTLED":
            assert rows[0]["billed_usd"] is None
            assert Decimal(balances["ai_spend_reserved_usd"]) == Decimal("0.30")
            assert balances["ai_spend_current"] == 0
        # Same persisted run/revision/rule/attempt must NEVER dispatch again,
        # even on another gate instance or after timeout/UNKNOWN.
        with pytest.raises(RuntimeError, match="usage unverified"):
            await _gate(gate.governed_context, provider).evaluate_rule(
                tenant, "R-SCOPE-CLARITY-01", _clause(),
            )
        assert len(provider.requests) == 1
        replay_rows, replay_balances = await _ledger(authority)
        assert len(replay_rows) == 1
        assert replay_balances["ai_spend_reserved_usd"] == balances["ai_spend_reserved_usd"]
        assert replay_balances["ai_spend_current"] == balances["ai_spend_current"]
    finally:
        await engine.dispose()


async def test_coherence_context_wrong_tenant_refuses_before_reservation(
    monkeypatch,
):
    authority, project = await _seed()
    _flags(monkeypatch)
    provider = StubProvider()
    wrong = replace(_identity(authority, project), tenant_id=uuid4())
    gate = _gate(wrong, provider)
    with pytest.raises(RuntimeError, match="trusted run"):
        await gate.evaluate_rule(
            str(authority.tenant_id), "R-SCOPE-CLARITY-01", _clause(),
        )
    assert provider.requests == []
    rows, _ = await _ledger(authority)
    assert rows == []



async def test_n4_n12_and_coherence_compete_for_same_tenant_cap(
    monkeypatch,
):
    """N4 and N12 holds deny Coherence until real receipt releases credit."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.coherence.adapters.ai.coherence_source_manifest import (
        CoherenceRevisionRef,
        verify_coherence_project_manifest,
    )
    from src.core.ai.budget_escrow_audit import audit_tenant_escrow
    from tests.integration.analysis.test_budget_escrow_audit_pg import _n4_hold
    from tests.integration.analysis.test_legacy_shared_reservations_pg import (
        _hold,
        _settle,
    )

    authority, project = await _seed(budget=0.55)
    engine = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
    )
    _patch_sessions(monkeypatch, engine)
    _flags(monkeypatch)
    monkeypatch.setenv("C2PRO_COHERENCE_RESERVE_USD", "0.20")
    provider = StubProvider(mode="negative")
    try:
        await _n4_hold(engine, authority, project, key="combined-n4-budget-001")
        n12 = await _hold(
            engine, authority.tenant_id, "combined-n12-budget-001", "0.20",
        )
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(authority.tenant_id)},
            )
            manifest = await verify_coherence_project_manifest(
                session, tenant_id=authority.tenant_id,
                project_id=project, run_id=uuid4(),
                revisions=(CoherenceRevisionRef(
                    authority.document_id, authority.revision_id,
                ),),
            )
        scoped_identity = manifest.bind_clause_source(
            document_id=authority.document_id,
            revision_id=authority.revision_id,
        )
        assert scoped_identity.source_sha256 == "a" * 64
        gate = _gate(scoped_identity, provider)
        with pytest.raises(RuntimeError, match="usage unverified"):
            await gate.evaluate_rule(
                str(authority.tenant_id), "R-SCOPE-CLARITY-01", _clause(),
            )
        assert provider.requests == []
        rows, budget_before = await _ledger(authority)
        assert len(rows) == 1
        assert budget_before["ai_spend_reserved_usd"] == Decimal("0.45")
        assert await _settle(
            engine, authority.tenant_id, n12.reservation_id, "0.08",
        ) == "SETTLED"
        decision = await gate.evaluate_rule(
            str(authority.tenant_id), "R-SCOPE-CLARITY-01", _clause(),
        )
        assert decision.state == "evaluated"
        assert decision.finding is None
        assert decision.cost_charged_usd == pytest.approx(0.12)
        assert len(provider.requests) == 1
        rows, balance = await _ledger(authority)
        assert len(rows) == 2
        assert balance["ai_spend_reserved_usd"] == Decimal("0.25")
        assert balance["ai_spend_current"] == pytest.approx(0.20)
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant',:t,true)"),
                {"t": str(authority.tenant_id)},
            )
            snapshot = await audit_tenant_escrow(
                session, tenant_id=authority.tenant_id,
            )
            assert snapshot.financial_reconciliation_passed
            assert snapshot.confirmed_spend_usd == Decimal("0.20")
            assert snapshot.n4.reserved_usd == Decimal("0.25")
            assert snapshot.legacy.reserved_usd == 0
    finally:
        await engine.dispose()
