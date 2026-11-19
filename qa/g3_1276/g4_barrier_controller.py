"""G4-LIVENESS-02 barrier-specific REAL Redis / separate Celery / PostgreSQL guard checks.
Imports only test-side seed/producer and exact SHA 916808 production guard functions.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import redis
from fastapi import HTTPException

from g4_controller import ROOT, DSN, BROKER, event, load_context, factory, tasks, router_mod
from src.documents.adapters.persistence.sqlalchemy_document_repository import SqlAlchemyDocumentRepository
from src.documents.application.n4_only_ingestion_effects_guard import (
    BEFORE_EFFECTS, MAY_HAVE_OCCURRED, GUARD_KEY, manual_claim_required,
)

def context_ids():
    ctx = load_context()
    return ctx, *(UUID(ctx[k]) for k in ("tenant_id", "document_id", "project_id", "owner_id", "revision_id"))

def event_rows():
    p = ROOT / "worker_events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x] if p.exists() else []

async def db_snapshot(db, document_id):
    row = await db.fetchrow("""
        SELECT op.generation, op.fencing_token, op.stage, op.phase, op.attempt_id,
               op.owner_token, op.lease_expires_at,
               doc.upload_status, doc.document_metadata
        FROM public.document_processing_operations op
          JOIN public.documents doc ON doc.id=op.document_id AND doc.tenant_id=op.tenant_id
        WHERE op.document_id=$1
    """, document_id)
    assert row is not None
    out = dict(row)
    if isinstance(out["document_metadata"], str):
        out["document_metadata"] = json.loads(out["document_metadata"])
    return out

async def check_killed(case):
    ctx, T, D, P, OWNER, REV = context_ids()
    before = case == "before"
    assert case in ("before", "after", "after-embedding")
    entries = event_rows()
    labels = [r["event"] for r in entries]
    marker = "KILLPOINT_BEFORE_EFFECTS_DURABLY_COMMITTED" if before else "KILLPOINT_UNSAFE_BARRIER_DURABLY_COMMITTED"
    assert marker in labels, labels
    assert "MAY_HAVE_OCCURRED_COMMITTED" not in labels if before else "MAY_HAVE_OCCURRED_COMMITTED" in labels
    assert not any(x in labels for x in ("N4_23_SETTLED", "FORBIDDEN_SIDE_EFFECT"))
    if case == "after-embedding":
        assert labels.count("RAGSERVICE_EMBEDDING_STUB_CALLED") == 1
    else:
        assert "RAGSERVICE_EMBEDDING_STUB_CALLED" not in labels

    db = await asyncpg.connect(DSN)
    try:
        row = await db_snapshot(db, D)
        assert str(row["stage"]) == "INGESTION" and str(row["phase"]) == "RUNNING"
        assert row["generation"] == 3 and row["fencing_token"] == 10
        assert row["upload_status"] == "processing", dict(row)  # DocumentStatus.PARSING storage value
        guard = row["document_metadata"]["n4_only_pilot"][GUARD_KEY]
        assert guard["state"] == (BEFORE_EFFECTS if before else MAY_HAVE_OCCURRED)
        assert guard["generation"] == 3 and guard["fencing_token"] == 10
        assert guard["document_revision_id"] == str(REV)
        assert guard["attempt_id"] == str(row["attempt_id"])
        assert row["lease_expires_at"] is not None
        assert await db.fetchval("SELECT count(*) FROM public.n4_extraction_runs WHERE document_id=$1", D) == 0
        assert await db.fetchval("""
            SELECT count(*) FROM public.n4_usage_reservations r
            JOIN public.n4_extraction_runs n ON n.run_id=r.run_id AND n.tenant_id=r.tenant_id
            WHERE n.document_id=$1
        """, D) == 0
        event("EXACT_KILL_COMMIT_ORDER_DB_VERIFIED", case=case, state=guard["state"], fence=10)
    finally:
        await db.close()
    eng, sessions = factory()
    try:
        async with sessions() as session:
            try:
                await router_mod.recover_n4_only_enqueue_endpoint(
                    P, D, OWNER, T, SqlAlchemyDocumentRepository(session),
                )
                raise AssertionError("active lease recovered")
            except HTTPException as exc:
                assert exc.status_code == 409
                await session.rollback()
                event("KILL_ACTIVE_LEASE_DENIED")
    finally:
        await eng.dispose()


async def expire_and_claim(case):
    ctx, T, D, P, OWNER, REV = context_ids()
    assert case in ("before", "after", "after-embedding")
    before = case == "before"
    db = await asyncpg.connect(DSN)
    try:
        row = await db_snapshot(db, D)
        assert row["fencing_token"] == 10
        assert row["document_metadata"]["n4_only_pilot"][GUARD_KEY]["state"] == (
            BEFORE_EFFECTS if before else MAY_HAVE_OCCURRED
        )
        await db.execute("""
            UPDATE public.document_processing_operations
            SET lease_expires_at=clock_timestamp() - interval '30 seconds'
            WHERE document_id=$1
        """, D)
        event("DB_CLOCK_LEASE_EXPIRED_SCRATCH_ONLY", case=case)
    finally:
        await db.close()

    # Also publish the ORIGINAL task with NO authority (replay attempt), not just
    # two copies of the same valid claimed grant. This must be refused by worker.
    tasks.process_document_async.apply_async(
        kwargs={"document_id": str(D), "revision_id": str(REV), "generation": 3},
        queue="document_parsing", task_id="g4-original-no-authority-" + str(uuid4()),
    )
    event("ORIGINAL_NO_AUTHORITY_REAL_REDIS_PUBLISHED")
    client = redis.Redis.from_url(BROKER)
    queue_before = client.llen("document_parsing")
    assert queue_before >= 2
    eng, sessions = factory()
    try:
        async with sessions() as session:
            if before:
                response = await router_mod.recover_n4_only_enqueue_endpoint(
                    P, D, OWNER, T, SqlAlchemyDocumentRepository(session),
                )
                assert response["status"] == "ENQUEUED", response
                assert response["generation"] == 3 and response["fencing_token"] == 11
                assert response["n4_billable_in_this_request"] is False
                event("OWNER_RECOVERY_BEFORE_EFFECTS_GEN3_FENCE11_PUBLISHED")
            else:
                try:
                    await router_mod.recover_n4_only_enqueue_endpoint(
                        P, D, OWNER, T, SqlAlchemyDocumentRepository(session),
                    )
                    raise AssertionError("UNSAFE guard accepted after crash/lease expiry")
                except HTTPException as exc:
                    assert exc.status_code == 409
                    await session.rollback()
                    event("UNSAFE_BARRIER_OWNER_RECOVERY_409_STOP")
    finally:
        await eng.dispose()
    queue_after = client.llen("document_parsing")
    if before:
        assert queue_after == queue_before + 1, (queue_before, queue_after)
    else:
        assert queue_after == queue_before, (queue_before, queue_after)
    event("REAL_REDIS_QUEUE_DISPATCH_COUNT_VERIFIED", before=queue_before, after=queue_after)

    db = await asyncpg.connect(DSN)
    try:
        row = await db_snapshot(db, D)
        assert row["generation"] == 3
        if before:
            assert row["fencing_token"] == 11 and row["phase"] == "CLAIMED"
            events = row["document_metadata"]["n4_only_pilot"]["enqueue_recovery_events"]
            assert len(events) == 2 and events[-1]["recovered_from_phase"] == "RUNNING"
            assert events[-1]["pre_effects_guard_verified"] is True
            assert events[-1]["claimed_fence"] == 11
            event("AUDIT_FENCE11_SAME_GENERATION_DURABLE", attempt_count=len(events))
        else:
            assert row["fencing_token"] == 10 and row["phase"] == "RUNNING"
            assert row["document_metadata"]["n4_only_pilot"][GUARD_KEY]["state"] == MAY_HAVE_OCCURRED
            event("UNSAFE_GUARD_UNCHANGED_AFTER_REJECT")
    finally:
        await db.close()


async def verify_redeliveries(case):
    ctx, T, D, P, OWNER, REV = context_ids()
    before = case == "before"
    import time
    done_marker = "N4_COMPLETED_REAL_WORKER" if before else "ORIGINAL_UNCLAIMED_REDELIVERY_DENIED"
    for _ in range(110):
        entries = event_rows()
        labels = [x["event"] for x in entries]
        if done_marker in labels and ("DUPLICATE_ADOPT_DENIED" in labels if before else True):
            break
        await asyncio.sleep(.4)
    else:
        raise AssertionError("worker did not finish the expected safe/unsafe redeliveries")
    labels = [x["event"] for x in entries]
    assert "FORBIDDEN_SIDE_EFFECT" not in labels
    assert "ORIGINAL_UNCLAIMED_REDELIVERY_DENIED" in labels, labels
    assert "DUPLICATE_ADOPT_DENIED" in labels, labels
    assert labels.count("BEFORE_EFFECTS_ADOPT_COMMITTED") == (2 if before else 1)
    if before:
        assert "MAY_HAVE_OCCURRED_COMMITTED" in labels
        assert labels.count("N4_23_SETTLED") == 1
        assert "N4_COMPLETED_REAL_WORKER" in labels
        assert "FAIL_FAST_SIDE_EFFECT_SPIES_ARMED" in labels
        assert "FINISH_INGESTION_AFTER_UNSAFE_BARRIER" in labels
        assert len({x["pid"] for x in entries if x["event"]=="BEFORE_EFFECTS_ADOPT_COMMITTED"}) == 2
    else:
        assert "N4_23_SETTLED" not in labels
        assert "ANALYSIS_ENQUEUED_REAL_BROKER" not in labels
        assert "RAGSERVICE_EMBEDDING_STUB_CALLED" in labels if case == "after-embedding" else True
    db = await asyncpg.connect(DSN)
    try:
        row = await db_snapshot(db, D)
        assert row["generation"] == 3
        run_count = await db.fetchval("SELECT count(*) FROM public.n4_extraction_runs WHERE document_id=$1", D)
        receipt_count = await db.fetchval("""
            SELECT count(*) FROM public.n4_usage_reservations r
            JOIN public.n4_extraction_runs n ON n.run_id=r.run_id AND n.tenant_id=r.tenant_id
            WHERE n.document_id=$1
        """, D)
        if before:
            assert run_count == 1 and receipt_count == 23
            assert row["fencing_token"] >= 11
            event("PRE_EFFECT_RECOVERED_N4_ONCE_23_SETTLED", runs=run_count, receipts=receipt_count)
        else:
            assert run_count == 0 and receipt_count == 0 and row["fencing_token"] == 10
            guard = row["document_metadata"]["n4_only_pilot"][GUARD_KEY]
            assert guard["state"] == MAY_HAVE_OCCURRED
            event("POST_UNSAFE_NO_DISPATCH_NO_RUN_ZERO_RECEIPTS", runs=0, receipts=0)
    finally:
        await db.close()
    if before:
        from g4_controller import verify
        # G4 generic verify expects CELERY_WORKER_ADOPT_ONCE from prior version;
        # validate GET directly without that obsolete expectation.
        eng, sessions = factory()
        try:
            async with sessions() as session:
                async with session.begin():
                    from sqlalchemy import text
                    await session.execute(text("SET TRANSACTION READ ONLY"))
                    data = await router_mod.read_n4_only_pilot_findings(
                        project_id=P, document_id=D, tenant_id=T, user_id=OWNER,
                        repo=SqlAlchemyDocumentRepository(session), offset=0, limit=30,
                    )
                    assert data["status"] == "COMPLETE" and data["total_findings"] == 23
                    assert data["n12_status"] == "UNASSESSED" and data["trusted"] is False
                    event("RECOVERED_READ_ONLY_GET_23_UNASSESSED")
        finally:
            await eng.dispose()
    event("ZERO_FORBIDDEN_N12_HITL_TRUST_SCORE", case=case)


if __name__ == "__main__":
    command = sys.argv[1]
    case = sys.argv[2]
    tasks_by_command = {
        "check": check_killed,
        "expire-claim": expire_and_claim,
        "verify": verify_redeliveries,
    }
    asyncio.run(tasks_by_command[command](case))
