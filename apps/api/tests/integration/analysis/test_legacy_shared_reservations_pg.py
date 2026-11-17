"""V4 S2 financial escrow: actual disposable PostgreSQL, no provider calls."""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.analysis.adapters.persistence.n4_incremental_store import (
    create_run,
    reserve_call,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.legacy_ai_reservation_store import (
    LegacyAIBudgetExceeded,
    LegacyAIReservationError,
    reconcile_legacy_ai,
    reserve_legacy_ai,
)
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority,
    _seed_caps,
    _seed_identity,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="needs migrated isolated PostgreSQL *_test"),
]


async def _seed(*, budget=1.0):
    a = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    conn = await asyncpg.connect(_DSN)
    try:
        await _seed_identity(conn, authority=a, project=project)
        await _seed_caps(conn, a.tenant_id, project, a.document_id, "3.000000")
        await conn.execute("""
            UPDATE public.tenants
               SET ai_budget_monthly=$2, ai_spend_last_reset=now() at time zone 'UTC'
             WHERE id=$1
        """, a.tenant_id, budget)
    finally:
        await conn.close()
    return a, project


def _engine():
    return create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )


async def _hold(engine, tenant, key, amount, source="N12_REVIEW"):
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.current_tenant', :tenant, true)"
        ), {"tenant": str(tenant)})
        return await reserve_legacy_ai(
            session, tenant_id=tenant, idempotency_key=key,
            source=source, max_charge_usd=amount,
        )


async def _settle(engine, tenant, reservation_id, cost, **usage):
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.current_tenant', :tenant, true)"
        ), {"tenant": str(tenant)})
        return await reconcile_legacy_ai(
            session, tenant_id=tenant, reservation_id=reservation_id,
            billed_usd=cost, **usage,
        )


async def _tenant_balances(tenant):
    conn = await asyncpg.connect(_DSN)
    try:
        return await conn.fetchrow("""
            SELECT ai_spend_current, ai_spend_reserved_usd FROM public.tenants
             WHERE id=$1
        """, tenant)
    finally:
        await conn.close()


async def test_parallel_legacy_requests_share_real_tenant_reservation_lock():
    a, _ = await _seed()
    engine = _engine()
    try:
        async def attempt(key):
            try:
                return (await _hold(engine, a.tenant_id, key, "0.75")).status
            except LegacyAIBudgetExceeded:
                return "DENIED"
        results = await asyncio.wait_for(asyncio.gather(
            attempt("legacy-call-parallel-A"), attempt("legacy-call-parallel-B"),
        ), timeout=9)
        assert sorted(results) == ["DENIED", "RESERVED"]
        balance = await _tenant_balances(a.tenant_id)
        assert Decimal(balance["ai_spend_reserved_usd"]) == Decimal("0.75")
        assert balance["ai_spend_current"] == 0
    finally:
        await engine.dispose()


async def test_unknown_cost_persists_then_settles_once_no_second_charge():
    a, _ = await _seed()
    engine = _engine()
    try:
        hold = await _hold(engine, a.tenant_id, "legacy-unknown-attempt", "0.60")
        replay = await _hold(engine, a.tenant_id, "legacy-unknown-attempt", "0.60")
        assert replay.replay and replay.reservation_id == hold.reservation_id
        with pytest.raises(LegacyAIReservationError, match="cannot change"):
            await _hold(engine, a.tenant_id, "legacy-unknown-attempt", "0.70")
        assert await _settle(
            engine, a.tenant_id, hold.reservation_id, None,
        ) == "UNKNOWN"
        balance = await _tenant_balances(a.tenant_id)
        assert balance["ai_spend_reserved_usd"] == Decimal("0.60")
        assert balance["ai_spend_current"] == 0

        assert await _settle(
            engine, a.tenant_id, hold.reservation_id, "0.40",
            input_tokens=325, output_tokens=180,
            provider_model="test-model",
        ) == "SETTLED"
        assert await _settle(
            engine, a.tenant_id, hold.reservation_id, "0.40",
            input_tokens=325, output_tokens=180,
            provider_model="test-model",
        ) == "SETTLED"
        with pytest.raises(LegacyAIReservationError, match="different usage"):
            await _settle(
                engine, a.tenant_id, hold.reservation_id, "0.40",
                input_tokens=326,
            )
        balance = await _tenant_balances(a.tenant_id)
        assert balance["ai_spend_current"] == pytest.approx(0.40)
        assert balance["ai_spend_reserved_usd"] == 0
    finally:
        await engine.dispose()


async def test_legacy_and_n4_compete_against_one_global_budget():
    a, project = await _seed()
    engine = _engine()
    try:
        windows = plan_n4_source_windows(
            "Every section must be inspected. " * 28,
            revision_id=str(a.revision_id), max_context_chars=600,
            overlap_chars=50,
        )
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            run_id = await create_run(
                session, authority=a, project_id=project,
                config_sha256="9"*64, windows=windows,
                budget_cap_usd="3.000000",
            )
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            n4 = await reserve_call(
                session, authority=a, run_id=run_id,
                window_ordinal=0, idempotency_key="n4-global-cross-ledger-0001",
                provider_model="test-model", estimated_max_usd="0.65",
                period_key="2026-11",
            )
            assert n4.status == "RESERVED"
        with pytest.raises(LegacyAIBudgetExceeded):
            await _hold(engine, a.tenant_id, "legacy-would-overdraw", "0.45")
        other = await _hold(engine, a.tenant_id, "legacy-approved-after-n4", "0.30")
        assert other.status == "RESERVED"
        balance = await _tenant_balances(a.tenant_id)
        assert balance["ai_spend_reserved_usd"] == Decimal("0.95")
    finally:
        await engine.dispose()


async def test_scope_isolation_including_wrong_tenant_receipt():
    a, _ = await _seed()
    engine = _engine()
    try:
        hold = await _hold(engine, a.tenant_id, "legacy-own-only-01", "0.10")
        with pytest.raises(LegacyAIReservationError, match="tenant"):
            async with AsyncSession(engine) as session, session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(uuid4())})
                await reserve_legacy_ai(
                    session, tenant_id=a.tenant_id, idempotency_key="wrong-scope",
                    source="N12_REVIEW", max_charge_usd="0.01",
                )
        other_tenant = uuid4()
        with pytest.raises(LegacyAIReservationError, match="tenant not found"):
            await _settle(engine, other_tenant, hold.reservation_id, "0.01")
    finally:
        await engine.dispose()


async def test_month_reset_does_not_drop_unknown_legacy_holds():
    a, _ = await _seed()
    engine = _engine()
    try:
        first = await _hold(engine, a.tenant_id, "first-legacy-prior-month", "0.55")
        assert await _settle(
            engine, a.tenant_id, first.reservation_id, None,
        ) == "UNKNOWN"
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("""
                UPDATE public.tenants
                   SET ai_spend_last_reset='2026-10-01'::timestamp,
                       ai_spend_current=0.20
                 WHERE id=$1
            """, a.tenant_id)
        finally:
            await conn.close()
        second = await _hold(engine, a.tenant_id, "legacy-new-month-attempt", "0.35")
        assert second.status == "RESERVED"
        balance = await _tenant_balances(a.tenant_id)
        assert balance["ai_spend_current"] == 0
        assert balance["ai_spend_reserved_usd"] == Decimal("0.90")
    finally:
        await engine.dispose()



async def test_database_enforces_immutable_escrow_amount_and_settled_receipt():
    a, _ = await _seed()
    engine = _engine()
    try:
        hold = await _hold(engine, a.tenant_id, "immutable-billable-call-1", "0.35")
        conn = await asyncpg.connect(_DSN)
        try:
            with pytest.raises(asyncpg.RaiseError, match="immutable"):
                await conn.execute("""
                    UPDATE public.legacy_ai_usage_reservations
                       SET reserved_usd=0.01
                     WHERE reservation_id=$1
                """, hold.reservation_id)
        finally:
            await conn.close()
        assert await _settle(
            engine, a.tenant_id, hold.reservation_id, "0.29",
        ) == "SETTLED"
        conn = await asyncpg.connect(_DSN)
        try:
            with pytest.raises(asyncpg.RaiseError, match="final"):
                await conn.execute("""
                    UPDATE public.legacy_ai_usage_reservations
                       SET billed_usd=0
                     WHERE reservation_id=$1
                """, hold.reservation_id)
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_legacy_ledger_rls_isolates_tenants_and_rejects_delete():
    a, _ = await _seed()
    engine = _engine()
    try:
        hold = await _hold(engine, a.tenant_id, "legacy-rls-001", "0.10")
        assert hold.status == "RESERVED"
        conn = await asyncpg.connect(_DSN)
        role = "n4_legacy_shared_rls_test"
        try:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=$1)", role,
            )
            if not exists:
                await conn.execute(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            await conn.execute(
                f"GRANT SELECT, INSERT, UPDATE ON "
                f"public.legacy_ai_usage_reservations TO {role}"
            )
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {role}")
                await conn.execute(
                    "SELECT set_config('app.current_tenant',$1,true)", str(uuid4()),
                )
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.legacy_ai_usage_reservations"
                ) == 0
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {role}")
                await conn.execute(
                    "SELECT set_config('app.current_tenant',$1,true)", str(a.tenant_id),
                )
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.legacy_ai_usage_reservations"
                ) == 1
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute(
                            "DELETE FROM public.legacy_ai_usage_reservations"
                        )
        finally:
            await conn.close()
    finally:
        await engine.dispose()
