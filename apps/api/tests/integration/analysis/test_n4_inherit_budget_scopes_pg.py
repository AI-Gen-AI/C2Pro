"""Disposable PostgreSQL test of inherited N4 sublimits; no model API calls.

Uses the guarded test_engine on a disposable PostgreSQL database; never production.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.analysis.adapters.persistence.n4_incremental_store import (
    N4BudgetExceeded,
    N4BudgetNotConfigured,
    account_call,
    create_run,
    reserve_call,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority,
    _seed_identity,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.alembic_schema]


def _scratch_dsn(test_engine) -> str:
    """test_engine runs its own OPS DB binding check before this function."""
    url = test_engine.url
    db_name = url.database or ""
    # Do not risk an external, shared or production DB when running these tests.
    if not (db_name.endswith("_test") or db_name.startswith("c2pro_ops_")):
        raise RuntimeError("N4 PG test requires disposable database identity")
    if url.host not in (None, "localhost", "127.0.0.1"):
        raise RuntimeError("N4 PG test refuses remote database host")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


async def _tenant_context(session: AsyncSession, tenant_id):
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant, true)"),
        {"tenant": str(tenant_id)},
    )


async def test_inherited_caps_no_duplicate_credit_and_default_fail_closed(test_engine):
    dsn = _scratch_dsn(test_engine)
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    source = "The EPC contractor shall provide notices to the Employer. " * 13
    windows = plan_n4_source_windows(
        source, revision_id=str(authority.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=authority, project=project)
        await conn.execute(
            """UPDATE public.tenants
                  SET ai_budget_monthly=5, ai_spend_current=0,
                      ai_spend_reserved_usd=0,
                      ai_spend_last_reset=clock_timestamp()
                WHERE id=$1""",
            authority.tenant_id,
        )
        # Only the approved tenant cap exists. Neither child is granted manually.
        await conn.execute(
            """INSERT INTO public.n4_budget_buckets
                 (tenant_id, scope_kind, scope_id, period_key, cap_usd)
               VALUES ($1, 'TENANT', $1, '2026-11', 5)""",
            authority.tenant_id,
        )
    finally:
        await conn.close()
    engine = create_async_engine(
        dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    try:
        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            run_id = await create_run(
                session, authority=authority, project_id=project,
                config_sha256="c" * 64, windows=windows,
                budget_cap_usd="5",
            )

        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            with pytest.raises(N4BudgetNotConfigured, match="absent"):
                await reserve_call(
                    session, authority=authority, run_id=run_id,
                    window_ordinal=0, idempotency_key="no-child-cap-001",
                    provider_model="test-model", estimated_max_usd="0.50",
                    period_key="2026-11",
                )
            count = await session.scalar(text("""
                SELECT count(*) FROM public.n4_budget_buckets
                 WHERE tenant_id=CAST(:tenant AS uuid)
                   AND scope_kind IN ('PROJECT','DOCUMENT')
            """), {"tenant": str(authority.tenant_id)})
            assert count == 0

        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            first = await reserve_call(
                session, authority=authority, run_id=run_id,
                window_ordinal=0, idempotency_key="approved-child-cap-001",
                provider_model="test-model", estimated_max_usd="0.50",
                period_key="2026-11", inherit_approved_scopes=True,
            )
            assert first.status == "RESERVED" and not first.replay
            balances = (await session.execute(text("""
                SELECT scope_kind, cap_usd, reserved_usd, spent_usd
                  FROM public.n4_budget_buckets
                 WHERE tenant_id=CAST(:tenant AS uuid)
                 ORDER BY scope_kind
            """), {"tenant": str(authority.tenant_id)})).mappings().all()
            assert len(balances) == 4
            assert all(Decimal(r["cap_usd"]) == Decimal("5") for r in balances)
            assert all(Decimal(r["reserved_usd"]) == Decimal("0.5") for r in balances)
            assert await account_call(
                session, authority=authority,
                reservation_id=first.reservation_id, billed_usd="0.01",
                actual_model_name="gpt-4.1", actual_provider="openai",
            ) == "SETTLED"

        # Child caps are NOT independent spending balances: the shared tenant
        # allowance has only $4.99 remaining after the first actual charge.
        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            with pytest.raises(N4BudgetExceeded, match="global tenant"):
                await reserve_call(
                    session, authority=authority, run_id=run_id,
                    window_ordinal=1, idempotency_key="over-tenant-cap-001",
                    provider_model="test-model", estimated_max_usd="5",
                    period_key="2026-11", inherit_approved_scopes=True,
                )
    finally:
        await engine.dispose()


async def test_inheritance_requires_explicit_tenant_cap_and_preserves_narrow_cap(test_engine):
    dsn = _scratch_dsn(test_engine)
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    windows = plan_n4_source_windows(
        "The owner requires delay notice. " * 25,
        revision_id=str(authority.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=authority, project=project)
        await conn.execute(
            """UPDATE public.tenants SET ai_budget_monthly=5,
               ai_spend_last_reset=clock_timestamp() WHERE id=$1""",
            authority.tenant_id,
        )
    finally:
        await conn.close()
    engine = create_async_engine(
        dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    try:
        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            run_id = await create_run(
                session, authority=authority, project_id=project,
                config_sha256="d" * 64, windows=windows,
                budget_cap_usd="5",
            )

        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            with pytest.raises(N4BudgetNotConfigured, match="TENANT budget"):
                await reserve_call(
                    session, authority=authority, run_id=run_id,
                    window_ordinal=0, idempotency_key="no-tenant-budget-001",
                    provider_model="test-model", estimated_max_usd="0.2",
                    period_key="2026-11", inherit_approved_scopes=True,
                )

        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                """INSERT INTO public.n4_budget_buckets
                   (tenant_id,scope_kind,scope_id,period_key,cap_usd)
                   VALUES ($1,'TENANT',$1,'2026-11',5),
                          ($1,'PROJECT',$2,'2026-11',0.1)""",
                authority.tenant_id, project,
            )
        finally:
            await conn.close()

        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            with pytest.raises(N4BudgetExceeded, match="PROJECT"):
                await reserve_call(
                    session, authority=authority, run_id=run_id,
                    window_ordinal=0, idempotency_key="narrow-project-cap-001",
                    provider_model="test-model", estimated_max_usd="0.2",
                    period_key="2026-11", inherit_approved_scopes=True,
                )
    finally:
        await engine.dispose()
