"""Disposable PostgreSQL test of inherited N4 sublimits; no model API calls.

Uses the guarded test_engine on a disposable PostgreSQL database; never production.
"""
from __future__ import annotations

from decimal import Decimal
from dataclasses import replace
from uuid import uuid4

import asyncpg
import asyncio
import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.analysis.adapters.persistence.n4_incremental_store import (
    N4BudgetExceeded,
    N4BudgetNotConfigured,
    account_call,
    block_window,
    create_run,
    progress,
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


async def _migrate_scratch(test_engine) -> str:
    """Apply the actual schema migrations only to an attested disposable DB."""
    dsn = _scratch_dsn(test_engine)
    async with test_engine.connect() as connection:
        before = await connection.scalar(text(
            "SELECT to_regclass('public.n4_budget_buckets')"
        ))
    if before is not None:
        return dsn
    api_dir = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["DATABASE_URL"] = dsn
    migration = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "heads",
        cwd=str(api_dir), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await migration.communicate()
    if migration.returncode != 0:
        raise RuntimeError(
            "Alembic scratch-only migration failed: "
            + (stderr or stdout)[-3000:].decode(errors="replace")
        )
    await test_engine.dispose()  # drop cached metadata after external schema creation
    async with test_engine.connect() as connection:
        after = await connection.scalar(text(
            "SELECT to_regclass('public.n4_budget_buckets')"
        ))
    if after is None:
        raise RuntimeError("Alembic reported success but N4 ledger schema is absent")
    return dsn


async def _tenant_context(session: AsyncSession, tenant_id):
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant, true)"),
        {"tenant": str(tenant_id)},
    )


async def test_inherited_caps_no_duplicate_credit_and_default_fail_closed(test_engine):
    dsn = await _migrate_scratch(test_engine)
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
    dsn = await _migrate_scratch(test_engine)
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


async def test_concurrent_inherited_reservations_share_one_tenant_cap(test_engine):
    """Two workers cannot each reserve more than the same shared $5."""
    dsn = await _migrate_scratch(test_engine)
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    windows = plan_n4_source_windows(
        "Contractor must notify the Employer. " * 50,
        revision_id=str(authority.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    assert len(windows) >= 2
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=authority, project=project)
        await conn.execute(
            """UPDATE public.tenants SET ai_budget_monthly=5,
                      ai_spend_current=0, ai_spend_reserved_usd=0,
                      ai_spend_last_reset=clock_timestamp()
                WHERE id=$1""", authority.tenant_id,
        )
        await conn.execute(
            """INSERT INTO public.n4_budget_buckets
                (tenant_id,scope_kind,scope_id,period_key,cap_usd)
               VALUES ($1,'TENANT',$1,'2026-11',5)""", authority.tenant_id,
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
                windows=windows, config_sha256="e" * 64,
                budget_cap_usd="5",
            )

        async def attempt(ordinal: int) -> str:
            try:
                async with AsyncSession(engine) as session, session.begin():
                    await _tenant_context(session, authority.tenant_id)
                    receipt = await reserve_call(
                        session, authority=authority, run_id=run_id,
                        window_ordinal=ordinal,
                        idempotency_key=f"concurrent-budget-{ordinal:04d}",
                        provider_model="test-model", estimated_max_usd="3",
                        period_key="2026-11", inherit_approved_scopes=True,
                    )
                return receipt.status
            except N4BudgetExceeded:
                return "DENIED"

        result = await asyncio.gather(attempt(0), attempt(1))
        assert sorted(result) == ["DENIED", "RESERVED"]
        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, authority.tenant_id)
            balances = (await session.execute(text("""
                SELECT scope_kind,reserved_usd,spent_usd
                  FROM public.n4_budget_buckets
                 WHERE tenant_id=CAST(:tenant AS uuid)
            """), {"tenant": str(authority.tenant_id)})).mappings().all()
            assert len(balances) == 4
            assert all(Decimal(r["reserved_usd"]) == Decimal("3") for r in balances)
            assert all(Decimal(r["spent_usd"]) == 0 for r in balances)
            actual = await session.scalar(text("""
                SELECT ai_spend_reserved_usd FROM public.tenants
                 WHERE id=CAST(:tenant AS uuid)
            """), {"tenant": str(authority.tenant_id)})
            assert Decimal(str(actual)) == Decimal("3")
    finally:
        await engine.dispose()


async def test_budget_blocked_zero_receipt_recovery_uses_new_fenced_generation(test_engine):
    """An entirely unpaid budget block permits a new generation, not replay billing."""
    dsn = await _migrate_scratch(test_engine)
    first_authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    windows = plan_n4_source_windows(
        "The contractor shall deliver all milestones. " * 35,
        revision_id=str(first_authority.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=first_authority, project=project)
        await conn.execute(
            """UPDATE public.tenants SET ai_budget_monthly=5,
                      ai_spend_last_reset=clock_timestamp()
                WHERE id=$1""", first_authority.tenant_id,
        )
        await conn.execute(
            """INSERT INTO public.n4_budget_buckets
                (tenant_id,scope_kind,scope_id,period_key,cap_usd)
               VALUES ($1,'TENANT',$1,'2026-11',5)""",
            first_authority.tenant_id,
        )
    finally:
        await conn.close()
    engine = create_async_engine(
        dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    try:
        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, first_authority.tenant_id)
            old_run = await create_run(
                session, authority=first_authority, project_id=project,
                windows=windows, config_sha256="f" * 64, budget_cap_usd="5",
            )
            await block_window(
                session, authority=first_authority, run_id=old_run,
                window_ordinal=0, reason="BUDGET_OR_RESERVATION_UNAVAILABLE",
            )
            old_status = await progress(
                session, tenant_id=first_authority.tenant_id, run_id=old_run,
            )
            assert old_status["examined_windows"] == 0

        new_authority = replace(
            first_authority, generation=2, fencing_token=2,
            attempt_id=uuid4(), owner_token=uuid4(),
        )
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                """UPDATE public.document_processing_operations
                   SET generation=2, fencing_token=2, phase='RUNNING',
                       attempt_id=$2, owner_token=$3,
                       lease_expires_at=clock_timestamp()+interval '1 hour'
                 WHERE document_id=$1""",
                first_authority.document_id,
                new_authority.attempt_id, new_authority.owner_token,
            )
        finally:
            await conn.close()

        async with AsyncSession(engine) as session, session.begin():
            await _tenant_context(session, new_authority.tenant_id)
            new_run = await create_run(
                session, authority=new_authority, project_id=project,
                windows=windows, config_sha256="f" * 64, budget_cap_usd="5",
            )
            assert new_run != old_run
            reserved = await reserve_call(
                session, authority=new_authority, run_id=new_run,
                window_ordinal=0, idempotency_key="recovered-new-generation-01",
                provider_model="test-model", estimated_max_usd="0.2",
                period_key="2026-11", inherit_approved_scopes=True,
            )
            assert reserved.status == "RESERVED"
            old_receipts = await session.scalar(text("""
                SELECT count(*) FROM public.n4_usage_reservations
                 WHERE tenant_id=CAST(:tenant AS uuid)
                   AND run_id=CAST(:old_run AS uuid)
            """), {"tenant": str(new_authority.tenant_id), "old_run": str(old_run)})
            assert old_receipts == 0
            old_status = await progress(
                session, tenant_id=new_authority.tenant_id, run_id=old_run,
            )
            assert old_status["status"] == "PARTIAL"
            assert old_status["examined_windows"] == 0
    finally:
        await engine.dispose()
