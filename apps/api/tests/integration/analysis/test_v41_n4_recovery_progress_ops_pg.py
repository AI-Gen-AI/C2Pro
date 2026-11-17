"""A-side N4 progress semantics on REAL Ops-owned PostgreSQL, no billable AI.

Uses the test_engine fixture: a job-private database with explicit C2PRO_OPS
binding, never the original disposed financial ledger or any production DSN.
"""
from __future__ import annotations

import runpy
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.analysis.application.n4_incremental_runner import N4IncrementalRunner
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority,
    _seed_caps,
    _seed_identity,
)
from tests.integration.analysis.test_n4_window_runner_pg import StubProvider, _source


async def _apply_scratch_migrations(engine):
    api_dir = Path(__file__).resolve().parents[3]
    migration_names = (
        "20261116_0001_n4_incremental_ledger.py",
        "20261116_0002_n4_window_blocked_provenance.py",
        "20261117_0001_n4_shared_tenant_reserved_budget.py",
    )
    async with engine.begin() as conn:
        existing_reserved_column = bool((await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='tenants'
               AND column_name='ai_spend_reserved_usd'
        """))).scalar_one_or_none())
        if not existing_reserved_column:
            raise AssertionError("Ops scratch tenant reserve column is absent")
        for migration_name in migration_names:
            # The Ops test bootstrap owns the tenants schema and holds a
            # seeded tenant session open. N4 progress needs its already-present
            # reserve column but must not ALTER tenants under that lock.
            if migration_name.startswith("20261117_0001"):
                continue
            migration = api_dir / "alembic/versions" / migration_name
            stmts = runpy.run_path(str(migration))["UPGRADE_STATEMENTS"]
            for statement in stmts:
                await conn.execute(text(statement))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ("missing_reference", "malformed_output"))
async def test_n4_progress_is_not_equivalent_to_billable_receipts(
    test_engine, test_tenant, failure_kind,
):
    await _apply_scratch_migrations(test_engine)
    authority = _new_authority(test_tenant.id, uuid4(), uuid4())
    project_id = uuid4()
    dsn = test_engine.url.render_as_string(hide_password=False)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(
            conn, authority=authority, project=project_id, create_tenant=False,
        )
        await _seed_caps(
            conn, authority.tenant_id, project_id,
            authority.document_id, "1.000000",
        )
    finally:
        await conn.close()

    provider = (
        StubProvider(missing_at=0)
        if failure_kind == "missing_reference"
        else StubProvider(malformed_at=0)
    )
    runner = N4IncrementalRunner(
        session_factory=async_sessionmaker(test_engine, expire_on_commit=False),
        provider=provider, enabled=True,
        run_cap_usd=Decimal("1.000000"),
        per_window_reservation_usd=Decimal("0.040000"),
        period_key="2026-11",
        max_context_chars=600, overlap_chars=50,
    )
    outcome = await runner.run(
        authority=authority, project_id=project_id,
        model_safe_text=_source(), n2_projection_attested=True,
    )
    assert outcome.status == "PARTIAL"
    if failure_kind == "missing_reference":
        assert outcome.examined_windows == outcome.total_windows - 1
        assert outcome.settled_receipt_windows == outcome.total_windows
        assert outcome.persisted_result_windows == outcome.total_windows
        assert outcome.blocked_result_windows == 1
        assert len(provider.calls) == outcome.total_windows
        replay = await runner.run(
            authority=authority, project_id=project_id,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert replay.persisted_result_windows == outcome.total_windows
        assert provider.calls == list(range(outcome.total_windows))
    else:
        assert outcome.examined_windows == 0
        assert outcome.settled_receipt_windows == 1
        assert outcome.persisted_result_windows == 0
        assert outcome.blocked_result_windows == 0
        assert provider.calls == [0]
