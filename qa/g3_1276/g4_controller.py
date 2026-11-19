"""G4 real Redis/Celery controller. Executed only against rootless private PostgreSQL.

Subcommands: seed-post, recover, verify, broker-down-check.
The separate worker module contains mocked N1/N2, StubProvider and negative spies.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.analysis.application.n4_only_pilot_policy import N4OnlyPilotScope
from src.core.tasks.celery_app import celery_app
from src.core.tasks import ingestion_tasks as tasks
from src.documents.adapters.http import router as router_mod
from src.documents.adapters.persistence.sqlalchemy_document_repository import SqlAlchemyDocumentRepository
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority, _seed_identity, _seed_caps,
)

ROOT = Path(os.environ["G4_RUN_DIR"])
DSN = os.environ["DATABASE_URL"]
assert DSN.startswith("postgresql://aigenadmin:@127.0.0.1:") and DSN.endswith("/c2pro_g3_1276_test")
BROKER = os.environ["CELERY_BROKER_URL"]
assert BROKER.startswith("redis://127.0.0.1:") and BROKER.endswith("/14")
celery_app.conf.update(
    broker_url=BROKER,
    result_backend=os.environ["CELERY_RESULT_BACKEND_URL"],
    broker_connection_retry=False, broker_connection_retry_on_startup=False,
    broker_transport_options={"socket_connect_timeout": 0.4, "socket_timeout": 1, "max_retries": 0},
    task_always_eager=False, task_publish_retry=False, task_default_queue="document_parsing",
)

def event(label: str, **extra: object):
    record = {"event": label, "pid": os.getpid(), **extra}
    with (ROOT / "controller_events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, sort_keys=True) + "\n")
        file.flush()
        os.fsync(file.fileno())
    print("G4_" + label, flush=True)


def load_context() -> dict:
    ctx = json.loads((ROOT / "context.json").read_text())
    for key, value in ctx["scope_env"].items():
        os.environ[key] = value
    return ctx


def factory():
    engine = create_async_engine(
        DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def seed_and_post():
    # Test a genuine disconnected local Redis before actual FastAPI enqueue.
    import redis
    try:
        redis.Redis.from_url(BROKER, socket_connect_timeout=0.3).ping()
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        event("BROKER_ACTUALLY_DOWN_BEFORE_POST")
    else:
        raise AssertionError("STOP: broker must be stopped for initial POST")
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    T, D, R = authority.tenant_id, authority.document_id, authority.revision_id
    P, OWNER, ENV = uuid4(), uuid4(), str(uuid4())
    source = None
    for n in range(35, 170):
        candidate = "\n\n".join(
            f"Clause {i}: synthetic project contractor must record each milestone, "
            "all exceptions and prior written notices before completion."
            for i in range(n)
        )
        if len(plan_n4_source_windows(candidate, revision_id=str(R), max_context_chars=600, overlap_chars=50)) == 23:
            source = candidate
            break
    assert source is not None
    scope = {
        "tenant_id": str(T), "project_id": str(P), "document_id": str(D),
        "revision_id": str(R), "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "approved_user_id": str(OWNER), "predecessor_generation": 2,
        "predecessor_fence": 8, "expected_windows": 23,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=40)).isoformat(),
    }
    approved = {
        "RAILWAY_ENVIRONMENT_NAME": "pilot",
        "RAILWAY_ENVIRONMENT_ID": ENV,
        "C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID": ENV,
        "C2PRO_N4_UAT_APPROVED_TENANT_ID": str(T),
        "C2PRO_N4_ONLY_APPROVED_SCOPE": json.dumps(scope),
        "C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED": "1",
    }
    # Synthetic environmental marker values only, no access to Railway or UAT.
    os.environ.update(approved)
    assert N4OnlyPilotScope.from_environment().next_generation == 3
    ctx = dict(
        tenant_id=str(T), document_id=str(D), revision_id=str(R),
        project_id=str(P), owner_id=str(OWNER), text=source, scope_env=approved,
    )
    (ROOT / "context.json").write_text(json.dumps(ctx))
    db = await asyncpg.connect(DSN)
    try:
        await _seed_identity(db, authority=authority, project=P)
        await _seed_caps(db, T, P, D, "5.000000")
        await db.execute("""
            UPDATE public.documents SET upload_status='error',
              document_metadata=jsonb_build_object('parsed_text_revision_id',$2::text)
            WHERE id=$1
        """, D, str(R))
        await db.execute("""
            UPDATE public.document_processing_operations
            SET generation=2, fencing_token=8, stage='ANALYSIS', phase='FAILED',
                outcome='fail_retryable', lease_expires_at=NULL
            WHERE document_id=$1
        """, D)
        await db.execute("""
            UPDATE public.tenants
            SET ai_budget_monthly=5, ai_spend_current=0, ai_spend_reserved_usd=0
            WHERE id=$1
        """, T)
    finally:
        await db.close()
    engine, sessions = factory()
    try:
        # No patch of production enqueue: this is actual Celery .delay() with Redis DOWN.
        async with sessions() as session:
            response = await router_mod.reprocess_n4_only_pilot_endpoint(
                P, D, OWNER, T, SqlAlchemyDocumentRepository(session)
            )
            assert response.task_id is None, response
        db = await asyncpg.connect(DSN)
        try:
            op = await db.fetchrow("""
                SELECT generation, fencing_token, stage, phase
                FROM public.document_processing_operations WHERE document_id=$1
            """, D)
            assert op["generation"] == 3 and op["fencing_token"] == 9, dict(op)
            event("POST_REAL_CAS_BROKER_OFFLINE_GEN3_FENCE9")
        finally:
            await db.close()
        async with sessions() as session:
            try:
                await router_mod.reprocess_n4_only_pilot_endpoint(
                    P, D, OWNER, T, SqlAlchemyDocumentRepository(session)
                )
                raise AssertionError("unexpected second generation")
            except HTTPException as exc:
                assert exc.status_code == 409
                await session.rollback()
                event("REPLAY_POST_DENIED_409")
    finally:
        await engine.dispose()


async def recover():
    ctx = load_context()
    T, D, P, OWNER = (UUID(ctx[key]) for key in ("tenant_id", "document_id", "project_id", "owner_id"))
    import redis
    assert redis.Redis.from_url(BROKER, socket_connect_timeout=1).ping()
    actual = tasks.process_document_async.apply_async
    published = []

    # Inject an application-side lost ACK *after actual successful Redis publish*.
    # This is NOT proof of a wire-level packet loss; it exercises B's unknown-ACK contract.
    def inject_ack_ambiguity(*args, **kwargs):
        task = actual(*args, **kwargs)
        published.append({"task_id": task.id, "kwargs": kwargs["kwargs"]})
        event("REAL_BROKER_TASK_PUBLISHED_ACK_LOST_INJECTED", task_id=task.id)
        raise ConnectionResetError("synthetic ACK loss after Redis accepted message")

    engine, sessions = factory()
    try:
        with patch.object(tasks.process_document_async, "apply_async", inject_ack_ambiguity):
            async with sessions() as session:
                response = await router_mod.recover_n4_only_enqueue_endpoint(
                    P, D, OWNER, T, SqlAlchemyDocumentRepository(session)
                )
                assert response["status"] == "BROKER_ACK_UNKNOWN_STOP", response
                assert response["generation"] == 3 and response["fencing_token"] == 10
                assert response["task_id"] is None
                event("RECOVER_REAL_BROKER_ACK_UNKNOWN_STOP_FENCE10")
        async with sessions() as session:
            try:
                await router_mod.recover_n4_only_enqueue_endpoint(
                    P, D, OWNER, T, SqlAlchemyDocumentRepository(session)
                )
                raise AssertionError("operator replay allowed during active lease")
            except HTTPException as exc:
                assert exc.status_code == 409
                await session.rollback()
                event("SECOND_RECOVERY_LEASE_DENIED_409")
        assert len(published) == 1
        # Confirm two real messages are accepted by the independent Redis broker.
        dispatch = published[0]
        tasks.process_document_async.apply_async(
            kwargs=dispatch["kwargs"], queue="document_parsing",
            task_id="g4-duplicate-same-authority-" + str(uuid4()),
        )
        event("REDIS_DUPLICATE_CELERY_MESSAGE_PUBLISHED")
        import redis
        client = redis.Redis.from_url(BROKER)
        count = client.llen("document_parsing")
        assert count >= 2, f"expected two real queue messages, got {count}"
        event("REAL_REDIS_QUEUE_MESSAGES", pending=count)
        (ROOT / "dispatch.json").write_text(json.dumps(dispatch))
    finally:
        await engine.dispose()


async def verify():
    ctx = load_context()
    T, D, P, OWNER = (UUID(ctx[key]) for key in ("tenant_id", "document_id", "project_id", "owner_id"))
    events_path = ROOT / "worker_events.jsonl"
    import time
    for _ in range(150):
        if events_path.exists():
            lines = [json.loads(line) for line in events_path.read_text().splitlines() if line]
            if any(e["event"] == "N4_COMPLETED_REAL_WORKER" for e in lines):
                break
        time.sleep(0.4)
    else:
        raise AssertionError("real worker did not complete N4 before deadline")
    all_events = [json.loads(line) for line in events_path.read_text().splitlines() if line]
    kinds = [e["event"] for e in all_events]
    assert kinds.count("CELERY_WORKER_ADOPT_ONCE") == 1, kinds
    assert "DUPLICATE_ADOPT_DENIED" in kinds, kinds
    assert kinds.count("N4_23_SETTLED") == 1, kinds
    assert "FORBIDDEN_SIDE_EFFECT" not in kinds, kinds
    assert "FAIL_FAST_SIDE_EFFECT_SPIES_ARMED" in kinds
    assert any(e["event"] == "N4_COMPLETED_REAL_WORKER" and e["provider_calls"] == 23 for e in all_events)
    worker_pids = {e["pid"] for e in all_events}
    assert os.getpid() not in worker_pids and len(worker_pids) == 1
    event("REAL_WORKER_SEPARATE_PROCESS_VERIFIED", worker_pid=list(worker_pids)[0])
    engine, sessions = factory()
    try:
        async with sessions() as session:
            async with session.begin():
                await session.execute(text("SET TRANSACTION READ ONLY"))
                data = await router_mod.read_n4_only_pilot_findings(
                    project_id=P, document_id=D, tenant_id=T, user_id=OWNER,
                    repo=SqlAlchemyDocumentRepository(session), offset=0, limit=25,
                )
                assert data["status"] == "COMPLETE" and data["total_findings"] == 23, data
                assert data["n12_status"] == "UNASSESSED" and data["trusted"] is False
                event("READ_ONLY_GET_REAL_PG_23_PROPOSED_N12_UNASSESSED")
        db = await asyncpg.connect(DSN)
        try:
            res = await db.fetchrow("""
                SELECT count(*) AS total,
                  count(*) FILTER (WHERE status='SETTLED') AS settled
                FROM public.n4_usage_reservations WHERE tenant_id=$1
            """, T)
            assert res["total"] == 23 and res["settled"] == 23, dict(res)
            budget = await db.fetchrow(
                "SELECT ai_spend_current, ai_spend_reserved_usd FROM public.tenants WHERE id=$1", T
            )
            assert float(budget["ai_spend_current"]) <= 5.0 and float(budget["ai_spend_reserved_usd"]) <= 5.0
            event("LEDGER_SINGLE_N4_RUN_23_SETTLED_CAP_SAFE")
        finally:
            await db.close()
        async with sessions() as session:
            try:
                await router_mod.read_n4_only_pilot_findings(
                    project_id=P, document_id=D, tenant_id=T, user_id=uuid4(),
                    repo=SqlAlchemyDocumentRepository(session), offset=0, limit=25,
                )
                raise AssertionError("wrong owner allowed")
            except HTTPException as exc:
                assert exc.status_code in (403, 404)
                await session.rollback()
                event("OWNER_MOCK_DENIED")
    finally:
        await engine.dispose()


def broker_down():
    import redis
    try:
        redis.Redis.from_url(BROKER, socket_connect_timeout=0.4).ping()
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        event("REAL_REDIS_BROKER_DOWN_CONFIRMED")
    else:
        raise AssertionError("broker should have been killed")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"seed-post": lambda: asyncio.run(seed_and_post()),
     "recover": lambda: asyncio.run(recover()),
     "verify": lambda: asyncio.run(verify()),
     "broker-down": broker_down}[cmd]()
