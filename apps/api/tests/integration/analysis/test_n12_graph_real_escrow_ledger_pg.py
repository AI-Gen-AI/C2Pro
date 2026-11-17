"""Real PG LangGraph N12 -> budget hold -> stub usage -> settled/unknown."""
from __future__ import annotations

import runpy
from decimal import Decimal
from pathlib import Path

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import text

from src.analysis.adapters.ai.anthropic_client import AIService
from src.analysis.adapters.graph import nodes, workflow
from tests.integration.analysis.test_legacy_ai_service_escrow_pg import _patch_sessions
from tests.integration.analysis.test_n12_checkpoint_escrow_pg import N12ResponseStub
from tests.integration.analysis.test_n12_graph_checkpoint_handoff_pg import (
    _graph_with_checkpointer,
    _no_temporal_gate,
    _state,
)

pytestmark = pytest.mark.asyncio


async def _ledger_snapshot(engine, tenant_id):
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :id, true)"),
            {"id": str(tenant_id)},
        )
        rows = (await conn.execute(text("""
            SELECT status, call_source, reserved_usd, billed_usd,
                   input_tokens, output_tokens, idempotency_key
              FROM public.legacy_ai_usage_reservations
             WHERE tenant_id=CAST(:id AS uuid)
        """), {"id": str(tenant_id)})).mappings().all()
        bal = (await conn.execute(text("""
            SELECT ai_spend_current, ai_spend_reserved_usd
              FROM public.tenants WHERE id=CAST(:id AS uuid)
        """), {"id": str(tenant_id)})).mappings().one()
        return [dict(r) for r in rows], dict(bal)


@pytest.mark.parametrize("measured_cost", [True, False])
async def test_n12_graph_real_pg_escrow_settles_or_retains_unknown(
    monkeypatch, test_engine, test_tenant, measured_cost,
):
    # Install the real additive Alembic ledger DDL in disposable Ops DB.
    migration = Path(__file__).resolve().parents[3] / (
        "alembic/versions/20261117_0002_legacy_ai_reservations.py"
    )
    sqls = runpy.run_path(str(migration))["UPGRADE_STATEMENTS"]
    async with test_engine.begin() as conn:
        for stmt in sqls:
            await conn.execute(text(stmt))

    state = _state()
    state["tenant_id"] = str(test_tenant.id)
    monkeypatch.setenv("C2PRO_N12_CHECKPOINT_ESCROW", "1")
    # Cross-front test: B's per-N12 latch also rejects missing escrow IDs.
    monkeypatch.setenv("C2PRO_N12_REQUIRE_ESCROW", "1")
    monkeypatch.setenv("C2PRO_LEGACY_AI_FULLSOURCE_RESERVE_USD", "0.35")
    monkeypatch.setenv("C2PRO_LEGACY_AI_FULLSOURCE_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("C2PRO_LEGACY_AI_FULLSOURCE_MAX_SEGMENTS", "2")
    monkeypatch.delenv("C2PRO_LEGACY_AI_ESCROW", raising=False)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "_apply_temporal_review_gate", _no_temporal_gate)
    _patch_sessions(monkeypatch, test_engine)

    class ObservedProvider(N12ResponseStub):
        def __init__(self):
            super().__init__()
            self.holds_seen = []

        async def generate(self, request):
            rows, balance = await _ledger_snapshot(test_engine, test_tenant.id)
            assert len(rows) == 1 and rows[0]["status"] == "RESERVED"
            assert rows[0]["reserved_usd"] == Decimal("0.350000")
            assert balance["ai_spend_reserved_usd"] == Decimal("0.350000")
            self.holds_seen.append(rows[0]["idempotency_key"])
            response = await super().generate(request)
            if not measured_cost:
                response.cost_usd = None
            return response

    provider = ObservedProvider()
    service = AIService(wrapper=provider, tenant_id=test_tenant.id)
    monkeypatch.setattr(nodes, "get_ai_service", lambda _tenant: service)

    async def no_error_db_write(_state, _node_result):
        return None

    monkeypatch.setattr(nodes, "_persist_node_error", no_error_db_write)
    url = test_engine.url.render_as_string(hide_password=False).replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    async with AsyncConnectionPool(
        conninfo=url, min_size=0, max_size=3, kwargs={"autocommit": True},
    ) as pool:
        saver = AsyncPostgresSaver(conn=pool)
        await saver.setup()
        graph = _graph_with_checkpointer(saver)
        monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
        cfg = {"configurable": {"thread_id": state["thread_id"]}}
        result = await graph.ainvoke(state, cfg, durability="sync")
        rows, balance = await _ledger_snapshot(test_engine, test_tenant.id)
        errors = [(n.node, getattr(getattr(n, "error", None), "error_type", None))
                  for n in result.get("node_results", [])]
        assert len(provider.calls) == 1, errors
        assert len(provider.holds_seen) == len(rows) == 1
        assert provider.holds_seen[0] == rows[0]["idempotency_key"]
        assert rows[0]["idempotency_key"].startswith("n12c-")
        assert rows[0]["call_source"] == "N12_FULL_SOURCE"
        assert provider.calls[0].metadata["full_source_analysis"] is True
        assert provider.calls[0].metadata["max_provider_segments"] == 2
        assert result["human_approval_required"] is True
        if measured_cost:
            assert rows[0]["status"] == "SETTLED"
            assert rows[0]["billed_usd"] == Decimal("0.160000")
            assert (rows[0]["input_tokens"], rows[0]["output_tokens"]) == (450, 70)
            assert balance["ai_spend_current"] == pytest.approx(0.16)
            assert balance["ai_spend_reserved_usd"] == 0
        else:
            assert rows[0]["status"] == "UNKNOWN"
            assert rows[0]["billed_usd"] is None
            assert balance["ai_spend_current"] == 0
            assert balance["ai_spend_reserved_usd"] == Decimal("0.350000")

        replay = await graph.ainvoke(dict(state), cfg, durability="sync")
        assert replay["human_approval_required"] is True
        assert len(provider.calls) == 1
        after, remaining = await _ledger_snapshot(test_engine, test_tenant.id)
        assert len(after) == 1 and after[0]["status"] == rows[0]["status"]
        assert remaining["ai_spend_reserved_usd"] == balance["ai_spend_reserved_usd"]


async def test_n12_strict_latch_refuses_unbudgeted_graph_call(monkeypatch):
    """Even with a working graph, N12 may never call provider without an ID."""
    from langgraph.checkpoint.memory import MemorySaver

    state = _state()
    provider = N12ResponseStub()
    service = AIService(wrapper=provider, tenant_id=state["tenant_id"])
    monkeypatch.setenv("C2PRO_N12_REQUIRE_ESCROW", "1")
    monkeypatch.setenv("C2PRO_N12_CHECKPOINT_ESCROW", "0")
    monkeypatch.delenv("C2PRO_LEGACY_AI_ESCROW", raising=False)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "get_ai_service", lambda _: service)
    monkeypatch.setattr(nodes, "_apply_temporal_review_gate", _no_temporal_gate)

    async def no_error_db_write(_state, _node_result):
        return None

    monkeypatch.setattr(nodes, "_persist_node_error", no_error_db_write)
    graph = _graph_with_checkpointer(MemorySaver())
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    result = await graph.ainvoke(
        state,
        {"configurable": {"thread_id": state["thread_id"]}},
        durability="sync",
    )
    assert provider.calls == []
    assert result["human_approval_required"] is True
    assert result["confidence_score"] is None
    # The N12 domain can normalize a refused provider operation to
    # UNASSESSED (a recorded critique node), rather than raising. Both paths
    # require HITL, and neither authorizes an unbudgeted provider call.
    assert any(n.node == "critique" for n in result["node_results"])
    assert "UNASSESSED" in str(result.get("critique_notes", "")).upper()
