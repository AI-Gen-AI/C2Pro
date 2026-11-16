"""Shared N4/legacy tenant escrow QA on a throwaway migrated PostgreSQL DB.

No model/provider calls. Tests cross-path accounting and concurrent reservations.
"""
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
    N4BudgetExceeded,
    account_call,
    create_run,
    reserve_call,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.cost_controller import BudgetExceededException, CostControllerService
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority,
    _seed_caps,
    _seed_identity,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="scratch DB *_test required"),
]


def _engine():
    assert "_test" in _DSN
    return create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )


async def _seed():
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    conn = await asyncpg.connect(_DSN)
    try:
        await _seed_identity(conn, authority=authority, project=project)
        await _seed_caps(
            conn, authority.tenant_id, project, authority.document_id, "3.000000",
        )
        await conn.execute("""
            UPDATE public.tenants
               SET ai_budget_monthly=1, ai_spend_last_reset=(now() at time zone 'UTC')
             WHERE id=$1
        """, authority.tenant_id)
    finally:
        await conn.close()
    return authority, project


def _windows(authority):
    return plan_n4_source_windows(
        ("Contract scope and exceptions must be reviewed in full. " * 18),
        revision_id=str(authority.revision_id),
        max_context_chars=600, overlap_chars=50,
    )


async def _run(engine, authority, project):
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.current_tenant', :tenant, true)"
        ), {"tenant": str(authority.tenant_id)})
        return await create_run(
            session, authority=authority, project_id=project,
            config_sha256="f" * 64, windows=_windows(authority),
            budget_cap_usd="3.000000",
        )


async def _reserve(engine, authority, run, amount, key):
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.current_tenant', :tenant, true)"
        ), {"tenant": str(authority.tenant_id)})
        return await reserve_call(
            session, authority=authority, run_id=run,
            window_ordinal=0, idempotency_key=key,
            provider_model="test-only", estimated_max_usd=amount,
            period_key="2026-11",
        )


async def test_n4_reserve_observed_by_legacy_and_settlement_not_double_counted():
    a, project = await _seed()
    engine = _engine()
    try:
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute(
                "UPDATE public.tenants SET ai_spend_current=0.60 WHERE id=$1",
                a.tenant_id,
            )
        finally:
            await conn.close()
        run = await _run(engine, a, project)
        reserve = await _reserve(engine, a, run, "0.30", "shared-escrow-001")
        assert reserve.status == "RESERVED"

        async with AsyncSession(engine) as session, session.begin():
            from src.core.tenants.service import TenantService
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            visible = await TenantService(session).get_budget_status(a.tenant_id)
            assert visible is not None
            assert visible.current_spend == pytest.approx(0.60)
            assert visible.reserved == pytest.approx(0.30)
            assert visible.remaining == pytest.approx(0.10)
            assert visible.usage_percentage == pytest.approx(90)

        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            controller = CostControllerService(session)
            with pytest.raises(BudgetExceededException):
                await controller.check_budget_availability(a.tenant_id, 0.20)
            await controller.check_budget_availability(a.tenant_id, 0.09)

        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            assert await account_call(
                session, authority=a, reservation_id=reserve.reservation_id,
                billed_usd="0.25", input_tokens=120, output_tokens=90,
            ) == "SETTLED"
            assert await account_call(
                session, authority=a, reservation_id=reserve.reservation_id,
                billed_usd="0.25", input_tokens=120, output_tokens=90,
            ) == "SETTLED"

        conn = await asyncpg.connect(_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT ai_spend_current, ai_spend_reserved_usd
                  FROM public.tenants WHERE id=$1
            """, a.tenant_id)
            assert row["ai_spend_current"] == pytest.approx(0.85)
            assert Decimal(row["ai_spend_reserved_usd"]) == 0
            recorded = await conn.fetchrow("""
                SELECT reserved_usd, spent_usd
                  FROM public.n4_budget_buckets
                 WHERE tenant_id=$1 AND scope_kind='TENANT'
            """, a.tenant_id)
            assert Decimal(recorded["spent_usd"]) == Decimal("0.25")
            assert Decimal(recorded["reserved_usd"]) == 0
        finally:
            await conn.close()
        with pytest.raises(N4BudgetExceeded, match="global tenant budget"):
            await _reserve(engine, a, run, "0.20", "shared-escrow-exceeds-001")
    finally:
        await engine.dispose()


async def test_global_cap_serializes_two_independent_n4_project_workers():
    a, project_a = await _seed()
    b = _new_authority(a.tenant_id, uuid4(), uuid4())
    project_b = uuid4()
    conn = await asyncpg.connect(_DSN)
    try:
        await _seed_identity(
            conn, authority=b, project=project_b, create_tenant=False,
        )
        await conn.execute("""
            INSERT INTO public.n4_budget_buckets
              (tenant_id, scope_kind, scope_id, period_key, cap_usd)
            VALUES ($1, 'PROJECT', $2, '2026-11', 3),
                   ($1, 'DOCUMENT', $3, '2026-11', 3)
        """, a.tenant_id, project_b, b.document_id)
    finally:
        await conn.close()
    engine = _engine()
    try:
        run_a, run_b = await asyncio.gather(
            _run(engine, a, project_a), _run(engine, b, project_b),
        )

        async def _try(authority, run_id, key):
            try:
                return (await _reserve(
                    engine, authority, run_id, "0.75", key,
                )).status
            except N4BudgetExceeded:
                return "DENIED"

        outcomes = await asyncio.wait_for(asyncio.gather(
            _try(a, run_a, "shared-global-A-001"),
            _try(b, run_b, "shared-global-B-001"),
        ), timeout=10)
        assert sorted(outcomes) == ["DENIED", "RESERVED"]
        conn = await asyncpg.connect(_DSN)
        try:
            global_pending = await conn.fetchval(
                "SELECT ai_spend_reserved_usd FROM public.tenants WHERE id=$1",
                a.tenant_id,
            )
            assert Decimal(global_pending) == Decimal("0.75")
            # The N4 TENANT bucket is 3 USD, so only GLOBAL cap blocks.
            buckets = await conn.fetchrow("""
                SELECT cap_usd, reserved_usd FROM public.n4_budget_buckets
                 WHERE tenant_id=$1 AND scope_kind='TENANT'
            """, a.tenant_id)
            assert Decimal(buckets["cap_usd"]) == 3
            assert Decimal(buckets["reserved_usd"]) == Decimal("0.75")
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_legacy_charge_and_n4_settlement_share_serialized_tenant_record():
    a, project = await _seed()
    engine = _engine()
    try:
        run = await _run(engine, a, project)
        reserved = await _reserve(engine, a, run, "0.60", "shared-charge-001")
        async with AsyncSession(engine) as session:
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            await CostControllerService(session).track_usage(a.tenant_id, 0.25)
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            await account_call(
                session, authority=a, reservation_id=reserved.reservation_id,
                billed_usd="0.55",
            )
        conn = await asyncpg.connect(_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT ai_spend_current, ai_spend_reserved_usd
                  FROM public.tenants WHERE id=$1
            """, a.tenant_id)
            assert row["ai_spend_current"] == pytest.approx(0.80)
            assert Decimal(row["ai_spend_reserved_usd"]) == 0
        finally:
            await conn.close()
    finally:
        await engine.dispose()



async def test_first_n4_charge_pins_month_and_legacy_cannot_reset_it():
    a, project = await _seed()
    engine = _engine()
    try:
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute(
                "UPDATE public.tenants SET ai_spend_last_reset=NULL WHERE id=$1",
                a.tenant_id,
            )
        finally:
            await conn.close()
        run = await _run(engine, a, project)
        hold = await _reserve(engine, a, run, "0.40", "initial-month-001")
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            await account_call(
                session, authority=a, reservation_id=hold.reservation_id,
                billed_usd="0.30",
            )
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            legacy = CostControllerService(session)
            with pytest.raises(BudgetExceededException):
                await legacy.check_budget_availability(a.tenant_id, 0.80)
        conn = await asyncpg.connect(_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT ai_spend_current, ai_spend_reserved_usd,
                       ai_spend_last_reset FROM public.tenants WHERE id=$1
            """, a.tenant_id)
            assert row["ai_spend_last_reset"] is not None
            assert row["ai_spend_current"] == pytest.approx(0.30)
            assert row["ai_spend_reserved_usd"] == 0
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_month_rollover_does_not_erase_unsettled_n4_reserve():
    a, project = await _seed()
    engine = _engine()
    try:
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("""
                UPDATE public.tenants SET
                    ai_spend_current=0.85,
                    ai_spend_last_reset='2026-10-15'::timestamp
                 WHERE id=$1
            """, a.tenant_id)
        finally:
            await conn.close()
        run = await _run(engine, a, project)
        hold = await _reserve(engine, a, run, "0.40", "month-reset-001")
        assert hold.status == "RESERVED"
        conn = await asyncpg.connect(_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT ai_spend_current, ai_spend_reserved_usd,
                       ai_spend_last_reset FROM public.tenants WHERE id=$1
            """, a.tenant_id)
            assert row["ai_spend_current"] == pytest.approx(0)
            assert row["ai_spend_reserved_usd"] == Decimal("0.40")
            assert row["ai_spend_last_reset"].year == 2026
            assert row["ai_spend_last_reset"].month == 11
        finally:
            await conn.close()
    finally:
        await engine.dispose()
