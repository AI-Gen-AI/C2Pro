"""Read-only escrow audit against actual disposable PostgreSQL 16.

No provider calls. The SQL mutations below are controlled corruption
fixtures on an isolated database whose name ends in *_test.
"""
from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.n4_incremental_store import (
    account_call,
    create_run,
    reserve_call,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.budget_escrow_audit import (
    TenantBudgetAuditError,
    audit_tenant_escrow,
)
from tests.integration.analysis.test_legacy_shared_reservations_pg import (
    _engine,
    _hold,
    _seed,
    _settle,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="isolated migrated *_test database required"),
]


async def _audit(engine, tenant, *, context_tenant=None, age=24):
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.current_tenant', :tenant, true)"
        ), {"tenant": str(context_tenant or tenant)})
        return await audit_tenant_escrow(
            session, tenant_id=tenant, stale_after_hours=age,
        )


async def _n4_hold(engine, authority, project, *, key="audit-n4-window-001"):
    windows = plan_n4_source_windows(
        "Contract requires review of all clauses and annexes. " * 18,
        revision_id=str(authority.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.current_tenant', :tenant, true)"
        ), {"tenant": str(authority.tenant_id)})
        run = await create_run(
            session, authority=authority, project_id=project,
            config_sha256="e"*64, windows=windows,
            budget_cap_usd="3.000000",
        )
        reserved = await reserve_call(
            session, authority=authority, run_id=run,
            window_ordinal=0, idempotency_key=key,
            provider_model="test-model", estimated_max_usd="0.25",
            period_key="2026-11",
        )
        return reserved


async def test_fresh_tenant_finance_audit_is_balanced():
    authority, _ = await _seed()
    engine = _engine()
    try:
        audit = await _audit(engine, authority.tenant_id)
        assert audit.financial_reconciliation_passed
        assert audit.findings == ()
        assert audit.calculated_escrow_usd == Decimal("0")
        assert audit.n4.reserved_count == 0
        assert audit.legacy.unknown_count == 0
        assert not audit.needs_provider_followup
    finally:
        await engine.dispose()


async def test_joint_n4_legacy_reservations_audit_then_reconcile():
    authority, project = await _seed()
    engine = _engine()
    try:
        n4 = await _n4_hold(engine, authority, project)
        legacy = await _hold(
            engine, authority.tenant_id, "audit-legacy-pending-001", "0.35",
        )
        combined = await _audit(engine, authority.tenant_id)
        assert combined.financial_reconciliation_passed
        assert combined.recorded_escrow_usd == Decimal("0.60")
        assert combined.calculated_escrow_usd == Decimal("0.60")
        assert combined.n4_tenant_bucket_reserved_usd == Decimal("0.25")
        assert combined.n4.reserved_count == 1
        assert combined.legacy.reserved_count == 1

        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(authority.tenant_id)})
            await account_call(
                session, authority=authority,
                reservation_id=n4.reservation_id, billed_usd="0.20",
            )
        assert await _settle(
            engine, authority.tenant_id, legacy.reservation_id, "0.30",
        ) == "SETTLED"
        finished = await _audit(engine, authority.tenant_id)
        assert finished.financial_reconciliation_passed
        assert finished.calculated_escrow_usd == 0
        assert finished.recorded_escrow_usd == 0
        assert finished.n4_tenant_bucket_reserved_usd == 0
        assert finished.confirmed_spend_usd == pytest.approx(0.50)
        assert not finished.needs_provider_followup
    finally:
        await engine.dispose()


async def test_detects_global_tenant_escrow_mismatch_not_silent_release():
    a, _ = await _seed()
    engine = _engine()
    try:
        await _hold(engine, a.tenant_id, "audit-global-mismatch-001", "0.20")
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("""
                UPDATE public.tenants SET
                    ai_spend_reserved_usd = ai_spend_reserved_usd + 0.07
                 WHERE id=$1
            """, a.tenant_id)
        finally:
            await conn.close()
        audit = await _audit(engine, a.tenant_id)
        assert not audit.financial_reconciliation_passed
        assert "GLOBAL_ESCROW_MISMATCH" in audit.findings
        assert audit.recorded_escrow_usd == Decimal("0.27")
        assert audit.calculated_escrow_usd == Decimal("0.20")
    finally:
        await engine.dispose()


async def test_detects_n4_bucket_mismatch_independently_of_global_escrow():
    a, project = await _seed()
    engine = _engine()
    try:
        await _n4_hold(engine, a, project)
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("""
                UPDATE public.n4_budget_buckets SET
                    reserved_usd = reserved_usd + 0.05
                 WHERE tenant_id=$1 AND scope_kind='TENANT'
            """, a.tenant_id)
        finally:
            await conn.close()
        audit = await _audit(engine, a.tenant_id)
        assert audit.recorded_escrow_usd == audit.calculated_escrow_usd
        assert not audit.financial_reconciliation_passed
        assert audit.findings == ("N4_TENANT_BUCKET_MISMATCH",)
    finally:
        await engine.dispose()


async def test_old_unknown_provider_receipt_flags_followup_never_releases_hold():
    a, _ = await _seed()
    engine = _engine()
    try:
        conn = await asyncpg.connect(_DSN)
        try:
            # A historical UNKNOWN receipt is born with an old timestamp:
            # the DB immutability trigger correctly prohibits rewriting it.
            # In the disposable DB seed the corresponding global liability.
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO public.legacy_ai_usage_reservations
                        (reservation_id, tenant_id, idempotency_key,
                         call_source, reserved_usd, status, created_at)
                    VALUES ($1, $2, 'audit-old-unknown-001',
                            'N12_REVIEW', 0.30, 'UNKNOWN',
                            clock_timestamp()-interval '48 hours')
                """, uuid4(), a.tenant_id)
                await conn.execute("""
                    UPDATE public.tenants SET
                        ai_spend_reserved_usd=ai_spend_reserved_usd+0.30
                     WHERE id=$1
                """, a.tenant_id)
        finally:
            await conn.close()
        audit = await _audit(engine, a.tenant_id, age=24)
        assert audit.financial_reconciliation_passed
        assert audit.needs_provider_followup
        assert audit.legacy.unknown_count == 1
        assert audit.legacy.stale_unknown_count == 1
        assert "UNRECONCILED_PROVIDER_USAGE" in audit.findings
        assert "STALE_UNKNOWN_PROVIDER_USAGE" in audit.findings
        assert audit.recorded_escrow_usd == Decimal("0.30")
    finally:
        await engine.dispose()


async def test_hard_cap_overage_flagged_but_not_falsely_called_corruption():
    a, _ = await _seed()
    engine = _engine()
    try:
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("""
                UPDATE public.tenants SET ai_spend_current=1.15
                 WHERE id=$1
            """, a.tenant_id)
        finally:
            await conn.close()
        audit = await _audit(engine, a.tenant_id)
        assert audit.financial_reconciliation_passed
        assert audit.findings == ("CAP_EXCEEDED_REQUIRES_REVIEW",)
    finally:
        await engine.dispose()


async def test_audit_fails_closed_for_wrong_tenant_or_missing_context():
    a, _ = await _seed()
    engine = _engine()
    try:
        with pytest.raises(TenantBudgetAuditError, match="context"):
            await _audit(engine, a.tenant_id, context_tenant=uuid4())
        with pytest.raises(TenantBudgetAuditError, match="tenant not found"):
            await _audit(engine, uuid4())
    finally:
        await engine.dispose()


@pytest.mark.parametrize("age", [0, -1, 721, 24.5, "24", True])
async def test_invalid_age_parameter_does_not_query_financial_ledgers(age):
    a, _ = await _seed()
    engine = _engine()
    try:
        with pytest.raises(ValueError, match="stale_after_hours"):
            await _audit(engine, a.tenant_id, age=age)
    finally:
        await engine.dispose()



async def test_snapshot_tenant_lock_serializes_with_concurrent_new_reserve():
    """Audit snapshot holds the tenant row while ledgers are read."""
    import asyncio

    a, _ = await _seed()
    engine = _engine()
    started = asyncio.Event()
    allow_exit = asyncio.Event()

    async def held_audit():
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            snapshot = await audit_tenant_escrow(
                session, tenant_id=a.tenant_id,
            )
            started.set()
            await allow_exit.wait()
            return snapshot

    task = asyncio.create_task(held_audit())
    holder = None
    try:
        await asyncio.wait_for(started.wait(), timeout=8)
        holder = asyncio.create_task(_hold(
            engine, a.tenant_id, "audit-lock-contention-001", "0.20",
        ))
        # The reservation requires tenant FOR UPDATE, blocked by audit's SHARE.
        done, pending = await asyncio.wait({holder}, timeout=0.25)
        assert not done and holder in pending
        allow_exit.set()
        snapshot = await asyncio.wait_for(task, timeout=8)
        assert snapshot.recorded_escrow_usd == 0
        hold = await asyncio.wait_for(holder, timeout=8)
        assert hold.status == "RESERVED"
        after = await _audit(engine, a.tenant_id)
        assert after.financial_reconciliation_passed
        assert after.recorded_escrow_usd == Decimal("0.20")
    finally:
        allow_exit.set()
        if not task.done():
            await task
        if holder is not None and not holder.done():
            await holder
        await engine.dispose()



async def test_n4_known_overage_reported_without_falsifying_unknown_usage():
    """N4 too: a known charge over its hold is SETTLED and auditable."""
    from src.analysis.adapters.persistence.n4_incremental_store import account_call

    a, project = await _seed(budget=1.0)
    engine = _engine()
    try:
        hold = await _n4_hold(
            engine, a, project, key="audit-n4-known-overage-001",
        )
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(a.tenant_id)},
            )
            await account_call(
                session, authority=a, reservation_id=hold.reservation_id,
                billed_usd="0.40",
            )
        report = await _audit(engine, a.tenant_id)
        assert report.financial_reconciliation_passed
        assert report.recorded_escrow_usd == 0
        assert report.confirmed_spend_usd == Decimal("0.40")
        assert report.n4.settled_overage_count == 1
        assert report.n4.settled_overage_usd == Decimal("0.15")
        assert "PROVIDER_CHARGE_EXCEEDED_RESERVATION" in report.findings
        assert report.needs_provider_followup
        assert report.n4.unknown_count == 0
    finally:
        await engine.dispose()
