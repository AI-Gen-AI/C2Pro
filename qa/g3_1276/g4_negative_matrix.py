"""G4 SHA916808 production recovery negative matrix on one disposable Alembic PG16.

Reuses a real worker-crash BEFORE_EFFECTS post-ADOPT fixture.
Every destructive change is strictly a scratch fixture and restored after a 409.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import redis
from fastapi import HTTPException

from g4_controller import BROKER, DSN, event, factory, router_mod, ROOT
from g4_barrier_controller import context_ids, db_snapshot
from src.documents.adapters.persistence.sqlalchemy_document_repository import SqlAlchemyDocumentRepository

async def deny_once(label: str, *, owner=None, tenant=None, project=None) -> None:
    # Do not call load_context() here: it would overwrite intentional
    # revoked/expired test env mutations and create a false positive.
    ctx = json.loads((ROOT / "context.json").read_text())
    T, D, P, OWNER, R = (UUID(ctx[k]) for k in (
        "tenant_id", "document_id", "project_id", "owner_id", "revision_id",
    ))
    client = redis.Redis.from_url(BROKER)
    size_before = client.llen("document_parsing")
    eng, sessions = factory()
    try:
        async with sessions() as session:
            try:
                await router_mod.recover_n4_only_enqueue_endpoint(
                    project or P, D, owner or OWNER, tenant or T,
                    SqlAlchemyDocumentRepository(session),
                )
            except HTTPException as exc:
                assert exc.status_code == 409, (label, exc.status_code)
                await session.rollback()
            else:
                raise AssertionError(f"NEGATIVE_WAS_ACCEPTED: {label}")
    finally:
        await eng.dispose()
    assert client.llen("document_parsing") == size_before, f"Unexpected broker dispatch in {label}"
    event("NEGATIVE_STOP_409", test=label)

async def main():
    ctx, T, D, P, OWNER, R = context_ids()
    db = await asyncpg.connect(DSN)
    try:
        start = await db_snapshot(db, D)
        assert start["phase"] == "RUNNING" and start["fencing_token"] == 10
        assert start["document_metadata"]["n4_only_pilot"]["ingestion_effects_guard"]["state"] == "ADOPTED_BEFORE_EFFECTS"
        assert await db.fetchval("SELECT count(*) FROM public.n4_extraction_runs WHERE document_id=$1", D) == 0

        await deny_once("LEASE_ACTIVE")
        await db.execute("""
            UPDATE public.document_processing_operations
            SET lease_expires_at=clock_timestamp() - interval '30 seconds'
            WHERE document_id=$1
        """, D)
        event("NEGATIVE_MATRIX_LEASE_EXPIRED_IN_SCRATCH")

        async def mutate_guard(label, *, key=None, value=None, remove=False):
            before = await db.fetchval(
                "SELECT document_metadata FROM public.documents WHERE id=$1", D,
            )
            metadata = json.loads(before) if isinstance(before, str) else dict(before)
            updated = json.loads(json.dumps(metadata))
            pilot = updated["n4_only_pilot"]
            if remove:
                pilot.pop("ingestion_effects_guard", None)
            elif key == "state":
                pilot["ingestion_effects_guard"]["state"] = value
            elif key == "source_sha256":
                pilot[key] = value
            elif key == "parsed_text_revision_id":
                updated[key] = value
            else:
                pilot["ingestion_effects_guard"][key] = value
            await db.execute(
                "UPDATE public.documents SET document_metadata=$2::jsonb WHERE id=$1",
                D, json.dumps(updated),
            )
            try:
                await deny_once(label)
            finally:
                await db.execute(
                    "UPDATE public.documents SET document_metadata=$2::jsonb WHERE id=$1",
                    D, json.dumps(metadata),
                )

        await mutate_guard("GUARD_MISSING", remove=True)
        await mutate_guard("GUARD_UNSAFE", key="state", value="EFFECTS_MAY_HAVE_OCCURRED")
        await mutate_guard("GUARD_TAMPERED", key="state", value="CORRUPTED")
        await mutate_guard("GUARD_STALE_FENCE", key="fencing_token", value=9)
        await mutate_guard("GUARD_STALE_ATTEMPT", key="attempt_id", value=str(uuid4()))
        await mutate_guard("GUARD_STALE_GENERATION", key="generation", value=2)
        await mutate_guard("GUARD_STALE_REVISION", key="document_revision_id", value=str(uuid4()))
        await mutate_guard("SOURCE_SHA_TAMPERED", key="source_sha256", value="f"*64)
        await mutate_guard("PARSED_REVISION_TAMPERED", key="parsed_text_revision_id", value=str(uuid4()))
        await deny_once("WRONG_OWNER", owner=uuid4())
        await deny_once("WRONG_TENANT", tenant=uuid4())
        await deny_once("WRONG_PROJECT", project=uuid4())
        enabled = os.environ.get("C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED")
        try:
            os.environ["C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED"] = "0"
            await deny_once("OPERATOR_REVOKED")
        finally:
            os.environ["C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED"] = enabled or "1"
        scope_raw = os.environ["C2PRO_N4_ONLY_APPROVED_SCOPE"]
        try:
            approved = json.loads(scope_raw)
            approved["expires_at"] = (datetime.now(UTC)-timedelta(seconds=5)).isoformat()
            os.environ["C2PRO_N4_ONLY_APPROVED_SCOPE"] = json.dumps(approved)
            await deny_once("SCOPE_EXPIRED")
        finally:
            os.environ["C2PRO_N4_ONLY_APPROVED_SCOPE"] = scope_raw

        async def tamper_operation(field, value, label):
            allowed = {
                "generation": "generation",
                "fencing_token": "fencing_token",
                "attempt_id": "attempt_id",
            }
            assert field in allowed
            current = await db.fetchval(
                f"SELECT {allowed[field]} FROM public.document_processing_operations WHERE document_id=$1", D,
            )
            await db.execute(
                f"UPDATE public.document_processing_operations SET {allowed[field]}=$2 WHERE document_id=$1",
                D, value,
            )
            try:
                await deny_once(label)
            finally:
                await db.execute(
                    f"UPDATE public.document_processing_operations SET {allowed[field]}=$2 WHERE document_id=$1",
                    D, current,
                )
        await tamper_operation("generation", 4, "OPERATION_STALE_GENERATION")
        await tamper_operation("fencing_token", 9, "OPERATION_STALE_FENCE")
        await tamper_operation("attempt_id", uuid4(), "OPERATION_STALE_ATTEMPT")

        # Historic N4 runs in ANY generation are STOP, even PARTIAL with no receipts.
        # Each row is an isolated fixture, rolled back by explicit fixture deletion
        # after the assertion; never a real customer history.
        async def historic_run(status: str | None):
            run_id = uuid4()
            await db.execute("""
                INSERT INTO public.n4_extraction_runs
                (run_id,tenant_id,project_id,document_id,document_revision_id,
                 source_sha256,config_sha256,generation,fencing_token,status,
                 total_windows,budget_cap_usd)
                VALUES($1,$2,$3,$4,$5,$6,$7,1,2,'PARTIAL',1,5)
            """, run_id, T, P, D, R, "a"*64, "b"*64)
            try:
                if status is not None:
                    await db.execute("""
                        INSERT INTO public.n4_extraction_windows
                        (tenant_id,run_id,ordinal,core_start,core_end,
                         context_start,context_end,context_sha256)
                        VALUES($1,$2,0,0,1,0,1,$3)
                    """, T, run_id, "c"*64)
                    await db.execute("""
                        INSERT INTO public.n4_usage_reservations
                        (reservation_id,tenant_id,run_id,window_ordinal,idempotency_key,
                         bucket_scopes,reserved_usd,spent_usd,status,model_name)
                        VALUES($1,$2,$3,0,$4,$5::jsonb,0.5,$6,$7,'stub')
                    """, uuid4(), T, run_id, "historic-"+status,
                    json.dumps(["tenant","project","document","run"]),
                    0.1 if status == "SETTLED" else None, status)
                await deny_once("HISTORIC_GEN1_PARTIAL_NO_RECEIPT" if status is None
                                else "HISTORIC_RECEIPT_"+status)
                event("HISTORIC_LEDGER_STOP_CONFIRMED", status=status or "PARTIAL_NO_RECEIPTS")
            finally:
                # Scratch fixture disposal only; the whole DB is destroyed on exit.
                await db.execute(
                    "DELETE FROM public.n4_usage_reservations WHERE run_id=$1", run_id,
                )
                await db.execute(
                    "DELETE FROM public.n4_extraction_windows WHERE run_id=$1", run_id,
                )
                await db.execute(
                    "DELETE FROM public.n4_extraction_runs WHERE run_id=$1", run_id,
                )
        for status in (None, "UNKNOWN", "RESERVED", "SETTLED", "CANCELED"):
            await historic_run(status)
        assert await db.fetchval("SELECT count(*) FROM public.n4_extraction_runs WHERE document_id=$1", D) == 0
    finally:
        await db.close()

    # Two truly concurrent owner commands on the same recovered-after-kill
    # state. Both use real DB transactions and the actual Redis publisher.
    ctx, T, D, P, OWNER, R = context_ids()
    async def try_recover():
        eng, sessions = factory()
        try:
            async with sessions() as session:
                try:
                    out = await router_mod.recover_n4_only_enqueue_endpoint(
                        P, D, OWNER, T, SqlAlchemyDocumentRepository(session),
                    )
                    return out
                except HTTPException as ex:
                    await session.rollback()
                    assert ex.status_code == 409
                    return {"status": "DENIED_409"}
        finally:
            await eng.dispose()
    client = redis.Redis.from_url(BROKER)
    q0 = client.llen("document_parsing")
    results = await asyncio.gather(try_recover(), try_recover())
    accepted = [x for x in results if x.get("status") == "ENQUEUED"]
    denied = [x for x in results if x.get("status") == "DENIED_409"]
    assert len(accepted)==1 and len(denied)==1, results
    assert accepted[0]["generation"] == 3 and accepted[0]["fencing_token"] == 11
    assert client.llen("document_parsing")==q0+1
    event("CONCURRENT_RECOVERY_ONE_FENCE11_ONE_409")
    await deny_once("ACTIVE_LEASE_AFTER_SECOND_CLAIM")
    db = await asyncpg.connect(DSN)
    try:
        await db.execute("""
            UPDATE public.document_processing_operations
            SET lease_expires_at=clock_timestamp()-interval '30 seconds'
            WHERE document_id=$1
        """, D)
        await deny_once("MAX_RECOVERY_CLAIMS_EXHAUSTED")
    finally:
        await db.close()
    event("NEGATIVE_MATRIX_COMPLETE_SAFE", cases=25)

if __name__ == "__main__":
    asyncio.run(main())
