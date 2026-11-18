"""#1274 exact offline transaction QA in disposable PG16; NEVER UAT.

Run only via:
    pg_virtualenv -v 16 bash -c 'psql -X -v ON_ERROR_STOP=1 -f ...platform_budget_pg_gate.sql && python .../platform_budget_write_pg_exercise.py'
Uses synthetic rows only and ephemeral aigenadmin's cluster-local superuser,
NOT a deployable platform budget write capability.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.admin.application.platform_budget_limit_service import (
    BudgetLimitConflict,
    BudgetLimitEditInput,
    apply_budget_limit_in_disposable_review,
)

TENANT = UUID("00000000-0000-0000-0000-0000000000a1")
ACTOR = "user_synthetic_only"
PERIOD = datetime.now(UTC).strftime("%Y-%m")


def request(expected: str, new: str, *, reason: str = "Approved offline fixture review") -> BudgetLimitEditInput:
    return BudgetLimitEditInput(
        tenant_id=TENANT, period_key=PERIOD,
        expected_cap_usd=Decimal(expected), new_cap_usd=Decimal(new),
        reason=reason, request_id=uuid4(), confirmed=True,
    )


async def verify() -> None:
    if not os.environ.get("PGHOST") or not os.environ.get("PGPORT"):
        raise RuntimeError("This test must run inside pg_virtualenv")
    url = URL.create(
        "postgresql+asyncpg",
        username=os.environ.get("PGUSER", "aigenadmin"),
        password=os.environ.get("PGPASSWORD"),
        host=os.environ["PGHOST"],
        port=int(os.environ["PGPORT"]),
        database=os.environ.get("PGDATABASE", "postgres"),
    )
    engine = create_async_engine(url, connect_args={"statement_cache_size": 0})
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE public.platform_budget_limit_audit(
                    request_id uuid PRIMARY KEY,
                    tenant_id uuid NOT NULL,
                    period_key text NOT NULL,
                    actor_clerk_id text NOT NULL,
                    before_cap_usd numeric(16,6) NOT NULL,
                    after_cap_usd numeric(16,6) NOT NULL,
                    reason text NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
        q = request("5", "4")
        async with maker() as db:
            result = await apply_budget_limit_in_disposable_review(
                db, request=q, owner_max_usd=Decimal("12"), actor_clerk_id=ACTOR,
            )
            assert result.previous_cap_usd == Decimal("5")
            assert result.new_cap_usd == Decimal("4")
        async with maker() as db:
            replay = await apply_budget_limit_in_disposable_review(
                db, request=q, owner_max_usd=Decimal("12"), actor_clerk_id=ACTOR,
            )
            assert replay == result

        async def totals() -> tuple[Decimal, Decimal, int]:
            async with engine.connect() as conn:
                a = (await conn.execute(text("SELECT ai_budget_monthly FROM public.tenants WHERE id=:id"), {"id":TENANT})).scalar_one()
                b = (await conn.execute(text("SELECT cap_usd FROM public.n4_budget_buckets WHERE tenant_id=:id AND scope_kind='TENANT'"), {"id":TENANT})).scalar_one()
                n = (await conn.execute(text("SELECT count(*) FROM public.platform_budget_limit_audit"))).scalar_one()
            return Decimal(a), Decimal(b), int(n)

        assert await totals() == (Decimal("4"), Decimal("4"), 1), "one audit + two caps"
        try:
            async with maker() as db:
                await apply_budget_limit_in_disposable_review(
                    db, request=request("5", "6"),
                    owner_max_usd=Decimal("12"), actor_clerk_id=ACTOR,
                )
            raise AssertionError("stale cap was accepted")
        except BudgetLimitConflict:
            pass

        try:
            async with maker() as db:
                await apply_budget_limit_in_disposable_review(
                    db, request=request("4", "1.49"),
                    owner_max_usd=Decimal("12"), actor_clerk_id=ACTOR,
                )
            raise AssertionError("cap below liabilities was accepted")
        except BudgetLimitConflict:
            pass

        # Trigger injects audit insertion failure after both cap UPDATE statements.
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE FUNCTION public.reject_budget_audit() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                  IF NEW.reason = 'TEST_AUDIT_FAILURE' THEN
                    RAISE EXCEPTION 'synthetic audit rejected';
                  END IF;
                  RETURN NEW;
                END
                $$
            """))
            await conn.execute(text("""
                CREATE TRIGGER budget_audit_failure BEFORE INSERT
                ON public.platform_budget_limit_audit
                FOR EACH ROW EXECUTE FUNCTION public.reject_budget_audit()
            """))
        try:
            async with maker() as db:
                await apply_budget_limit_in_disposable_review(
                    db, request=request("4", "5", reason="TEST_AUDIT_FAILURE"),
                    owner_max_usd=Decimal("12"), actor_clerk_id=ACTOR,
                )
            raise AssertionError("audit failure did not rollback caps")
        except Exception as exc:
            assert "synthetic audit rejected" in str(exc), type(exc).__name__
        assert await totals() == (Decimal("4"), Decimal("4"), 1), "rollback on failed audit"

        # Simulate reserve_call holding the tenant row first. The update must
        # await commit and then reject a cap below newly held reservations.
        async def race_edit() -> bool:
            try:
                async with maker() as db:
                    await apply_budget_limit_in_disposable_review(
                        db, request=request("4", "3.4"),
                        owner_max_usd=Decimal("12"), actor_clerk_id=ACTOR,
                    )
            except BudgetLimitConflict as exc:
                return "below spend" in str(exc)
            return False

        async with maker() as blocker:
            async with blocker.begin():
                await blocker.execute(
                    text("SELECT id FROM public.tenants WHERE id=:id FOR UPDATE"),
                    {"id":TENANT},
                )
                await blocker.execute(
                    text("UPDATE public.tenants SET ai_spend_reserved_usd=2.5 WHERE id=:id"),
                    {"id":TENANT},
                )
                await blocker.execute(
                    text("UPDATE public.n4_budget_buckets SET reserved_usd=2.5 WHERE tenant_id=:id AND scope_kind='TENANT'"),
                    {"id":TENANT},
                )
                task = asyncio.create_task(race_edit())
                await asyncio.sleep(0.2)
                assert not task.done(), "tenant lock did not serialize budget writer"
        assert await task, "writer failed to account for newly reserved liabilities"
        assert await totals() == (Decimal("4"), Decimal("4"), 1)
        print("PG_WRITE_TRANSACTION_PASS: both caps atomic, audit idempotent, stale denied, rollback, reserve race serialized")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
