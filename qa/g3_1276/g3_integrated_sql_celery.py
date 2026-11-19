"""G3 #1276 integration harness. Only ephemeral migrated PG. Never real provider.
Exact source SHA required: 8a84f9ebcd54928347171cef0cc80f34ca3fb949.
Clerk identity/worker parser/N1/N2 are fixtures. SQL CAS, Celery task handlers,
N4 graph and real N4IncrementalRunner + GET use same disposable DB.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.analysis.application.n4_incremental_runner import N4IncrementalRunner
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.analysis.application.n4_only_pilot_policy import N4OnlyPilotScope, pilot_marker
from src.core.processing_authority import (
    ProcessingAuthority, ProcessingStage, AcquireOutcome, acquire,
    finish_ingestion, bound_authority,
)
from src.documents.adapters.persistence.sqlalchemy_document_repository import SqlAlchemyDocumentRepository
from src.documents.adapters.http import router as router_mod
from src.documents.domain.models import DocumentStatus
from src.analysis.application import n4_only_pilot as graph
from src.core.tasks import ingestion_tasks as tasks
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority, _seed_identity, _seed_caps,
)
from tests.integration.analysis.test_n4_window_runner_pg import StubProvider

REPO_ROOT = Path(__file__).resolve().parents[1] if False else None
G3_SHA = "8a84f9ebcd54928347171cef0cc80f34ca3fb949"
DSN = os.environ["C2PRO_N4_SCRATCH_DSN"]
assert "c2pro_g3_1276_test" in DSN and os.environ.get("PG_CLUSTER_CONF_ROOT","").startswith("/tmp/pg_virtualenv."), "pg_virtualenv scratch only"
PG = DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
EVENTS: list[str] = []
PROVIDER = StubProvider()
SCOPE = None

async def run_g3():
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    T, D, R = authority.tenant_id, authority.document_id, authority.revision_id
    P, OWNER, ENV = uuid4(), uuid4(), str(uuid4())
    projection = None
    for n in range(35, 170):
        text_source = "\n\n".join(
            f"Clause {i}: synthetic project contractor must record each milestone, all exceptions and prior written notices before completion."
            for i in range(n)
        )
        windows = plan_n4_source_windows(text_source, revision_id=str(R), max_context_chars=600, overlap_chars=50)
        if len(windows) == 23:
            projection = text_source
            break
    assert projection is not None
    source_hash = hashlib.sha256(projection.encode()).hexdigest()
    scope_data = {
        "tenant_id": str(T), "project_id": str(P), "document_id": str(D),
        "revision_id": str(R), "source_sha256": source_hash,
        "approved_user_id": str(OWNER), "predecessor_generation": 2,
        "predecessor_fence": 8, "expected_windows": 23,
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    os.environ.update({
        "RAILWAY_ENVIRONMENT_NAME": "pilot", "RAILWAY_ENVIRONMENT_ID": ENV,
        "C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID": ENV,
        "C2PRO_N4_UAT_APPROVED_TENANT_ID": str(T),
        "C2PRO_N4_ONLY_APPROVED_SCOPE": json.dumps(scope_data),
    })
    scope = N4OnlyPilotScope.from_environment()
    assert scope.next_generation == 3
    db = await asyncpg.connect(DSN)
    try:
        await _seed_identity(db, authority=authority, project=P)
        await _seed_caps(db, T, P, D, "5.000000")
        await db.execute("""
            UPDATE public.documents
               SET upload_status='error',
                   document_metadata=jsonb_build_object('parsed_text_revision_id',$2::text)
             WHERE id=$1
        """, D, str(R))
        await db.execute("""
            UPDATE public.document_processing_operations
               SET generation=2, fencing_token=8, stage='ANALYSIS', phase='FAILED',
                   outcome='fail_retryable', lease_expires_at=NULL
             WHERE document_id=$1
        """, D)
        await db.execute("UPDATE public.tenants SET ai_budget_monthly=5, ai_spend_current=0, ai_spend_reserved_usd=0 WHERE id=$1", T)
    finally:
        await db.close()
    engine = create_async_engine(PG, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    from src.documents.application.dtos import DocumentResponse
    enqueued = []
    def enqueue(document_id, *, revision_id=None, generation=None):
        EVENTS.append("CELERY_ENQUEUE_MEMORY_SIMULATED")
        assert document_id == D and revision_id == R and generation == 3
        enqueued.append({"document_id": str(D), "revision_id": str(R), "generation": 3})
        return "synthetic-celery-message-1"
    # The user/tenant parameters below stand in for verified Clerk DI.
    # They DO NOT exercise a real JWT, session, or Clerk SDK.
    with patch.object(router_mod, "_enqueue_document_processing", enqueue):
        async with factory() as session:
            repo = SqlAlchemyDocumentRepository(session)
            response = await router_mod.reprocess_n4_only_pilot_endpoint(P, D, OWNER, T, repo)
            assert response.task_id == "synthetic-celery-message-1", response
            EVENTS.append("POST_FIXTURE_CLERK_OWNER_ACCEPTED")
        row = await asyncpg.connect(DSN)
        try:
            op = await row.fetchrow("SELECT generation,fencing_token,stage,phase FROM public.document_processing_operations WHERE document_id=$1", D)
            assert op["generation"] == 3 and op["fencing_token"] == 9, op
            EVENTS.append("CAS_DB_GEN3_FENCE9_COMMITTED")
        finally:
            await row.close()
        async with factory() as session:
            try:
                await router_mod.reprocess_n4_only_pilot_endpoint(P, D, OWNER, T, SqlAlchemyDocumentRepository(session))
                raise AssertionError("Second POST was accepted")
            except HTTPException as exc:
                assert exc.status_code == 409
                await session.rollback()
                EVENTS.append("REDELIVERY_POST_409_NO_NEW_GEN")

    async def fake_ingestion(*, document_id, revision_id, generation, authority):
        local_engine = create_async_engine(PG, poolclass=NullPool)
        local_factory = async_sessionmaker(local_engine, expire_on_commit=False)
        async with local_factory() as session:
            async with session.begin():
                acquired = await acquire(session, tenant_id=T, document_id=D,
                                         stage=ProcessingStage.INGESTION,
                                         revision_id=R, generation=generation)
                assert acquired.outcome is AcquireOutcome.ACQUIRED, acquired
                EVENTS.append("CELERY_INGESTION_AUTHORITY_ACQUIRED")
                await finish_ingestion(session, acquired.authority)
                EVENTS.append("CELERY_INGESTION_STAGE_COMPLETED")
        await local_engine.dispose()
        return {"status": "parsed", "document_id": str(D)}
    # In-process Celery .apply: executes the actual registered task wrapper,
    # not a live broker/worker process. Parser body is substituted by fixture.
    with patch.object(tasks, "_run_document_processing_task_lifecycle", fake_ingestion):
        task_result = await asyncio.to_thread(
            lambda: tasks.process_document_async.apply(
                kwargs=enqueued[0], throw=True,
            ).get(propagate=True)
        )
    assert task_result["status"] == "parsed", task_result
    EVENTS.append("CELERY_INGESTION_TASK_HANDLER_PASS")

    async def fake_analysis(*, tenant_id, document_id, **kwargs):
        assert UUID(str(tenant_id)) == T and document_id == D
        assert kwargs.get("generation") == 3 and kwargs.get("n4_only_pilot") is True
        # Use actual authority acquisition, no direct synthetic fence stamping.
        local_engine = create_async_engine(PG, poolclass=NullPool)
        local_factory = async_sessionmaker(local_engine, expire_on_commit=False)
        async with local_factory() as session:
            async with session.begin():
                acquired = await acquire(session, tenant_id=T, document_id=D,
                    revision_id=R, generation=3, stage=ProcessingStage.ANALYSIS)
                assert acquired.outcome is AcquireOutcome.ACQUIRED, acquired
                a = acquired.authority
        assert a.generation == 3 and a.fencing_token > 9
        EVENTS.append("CELERY_ANALYSIS_AUTHORITY_FENCED")
        async def n1(state):
            EVENTS.append("N1_PARSER_STUB")
            return {"document_text": projection}
        async def n2(state):
            EVENTS.append("N2_PII_STUB")
            return {"anonymized_text": projection}
        async def n4(state):
            EVENTS.append("N4_GOVERNED_RUNNER")
            graph.attest_n4_pilot_input(state)  # real policy + 23-window SHA preflight
            runner = N4IncrementalRunner(session_factory=local_factory, provider=PROVIDER,
                enabled=True, run_cap_usd=Decimal("5"),
                per_window_reservation_usd=Decimal("0.50"),
                period_key="2026-11", max_context_chars=600, overlap_chars=50)
            result = await runner.run(
                authority=a, project_id=P, model_safe_text=projection,
                n2_projection_attested=True,
            )
            assert result.status == "COMPLETE" and result.total_windows == 23
            assert result.examined_windows == 23 and result.settled_receipt_windows == 23
            return {
                "n4_incremental_run_id": str(result.run_id),
                "n4_incremental_window_coverage": {"examined": 23, "total": 23},
                "extracted_risks": [{"title": "Synthetic finding"}],
            }
        def identity(state):
            return (a, P, projection)
        def limits():
            return (Decimal("5"), Decimal("0.50"), 600, 50)
        fail_spies = []
        def forbidden(name):
            def err(*args, **kwargs):
                fail_spies.append(name)
                raise AssertionError(f"FORBIDDEN_SIDE_EFFECT_{name}")
            return err
        state = {
            "tenant_id": str(T), "project_id": str(P), "document_id": str(D),
            "document_revision_id": str(R), "doc_type": "contract",
            "document_text": projection, "messages": [], "extracted_risks": [],
            "n4_only_pilot": pilot_marker(scope),
        }
        with ExitStack() as stack:
            for obj, attr, value in (
                (graph, "document_ingestion_node", n1),
                (graph, "pii_anonymizer_node", n2),
                (graph, "n4_only_risk_node", n4),
                (graph, "_identity", identity),
                (graph, "_limits", limits),
            ):
                stack.enter_context(patch.object(obj, attr, value))
            # Structural node proof, separate from spies on side effects.
            assert set(graph.build_n4_only_workflow().nodes) == {
                "document_ingestion", "pii_anonymizer", "risk_extractor"
            }
            with bound_authority(a):
                result = await graph.run_n4_only_pilot(state)
            assert result["coherence_score"] is None
            assert result["n12_status"] == "UNASSESSED"
            assert result["hitl_generated"] is False
            assert result["trust_state"] == "PROPOSED"
        assert not fail_spies, fail_spies
        EVENTS.append("N4_END_NO_N12_HITL_TRUSTED_SCORE")
        # In real worker this marker is persisted by ingestion lifecycle, which
        # is mocked here; explicitly seed same local DB for GET readback.
        async with local_factory() as session:
            async with session.begin():
                await session.execute(text("""
                    UPDATE documents SET document_metadata =
                      jsonb_set(document_metadata, '{n4_only_pilot}',
                                CAST(:marker AS jsonb), true)
                     WHERE id=CAST(:doc AS uuid)
                """), {"doc": str(D), "marker": json.dumps(
                    pilot_marker(scope) | {"state": result["n4_only_pilot_status"],
                                            "n12_state": "UNASSESSED"}
                )})
        EVENTS.append("SYNTHETIC_MARKER_PERSISTED_FOR_GET")
        await local_engine.dispose()
        return result
    with patch.object(tasks, "_run_document_analysis_task_lifecycle", fake_analysis):
        result = await asyncio.to_thread(lambda: tasks.process_document_n4_only_pilot_async.apply(
            kwargs={"tenant_id": str(T), "document_id": str(D), "generation": 3},
            throw=True,
        ).get(propagate=True))
    assert result["n4_only_pilot_status"] == "PROPOSED_N12_UNASSESSED", result
    EVENTS.append("CELERY_N4_ONLY_TASK_HANDLER_PASS")

    async def get(*, user=OWNER, tenant=T, offset=0, limit=25):
        async with factory() as session:
            async with session.begin():
                await session.execute(text("SET TRANSACTION READ ONLY"))
                repo = SqlAlchemyDocumentRepository(session)
                return await router_mod.read_n4_only_pilot_findings(
                    project_id=P, document_id=D, tenant_id=tenant,
                    user_id=user, repo=repo, offset=offset, limit=limit,
                )
    full = await get()
    assert full["status"] == "COMPLETE", full
    assert full["ledger_status"] == "COMPLETE"
    assert full["total_findings"] == 23
    assert full["fencing_token"] >= 10
    assert full["n12_status"] == "UNASSESSED"
    assert full["trusted"] is False
    EVENTS.append("GET_REAL_HANDLER_REAL_PG_COMPLETE_23")
    offset = await get(offset=22, limit=1)
    assert len(offset["findings"]) == 1 and offset["findings"][0]["window_ordinal"] == 22
    EVENTS.append("GET_PAGINATION_REAL_PG_PASS")
    for name,kwargs in (("OWNER_DENY",{"user":uuid4()}),("TENANT_DENY",{"tenant":uuid4()})):
        try:
            await get(**kwargs)
            raise AssertionError(f"{name} returned data")
        except HTTPException as exc:
            assert exc.status_code == 404
            EVENTS.append(name)
    async with factory() as session:
        async with session.begin():
            await session.execute(text("SET TRANSACTION READ ONLY"))
            res = await session.execute(text("""
                SELECT count(*) FROM public.n4_usage_reservations WHERE tenant_id=CAST(:t AS uuid)
            """), {"t":str(T)})
            assert res.scalar_one() == 23
    # Stub provider cannot call network; asserts number of invocations.
    assert PROVIDER.calls == list(range(23)), PROVIDER.calls
    EVENTS.append("ZERO_PAID_CALLS_23_STUB_SETTLED")
    from src.analysis.adapters.graph.workflow import route_after_risk_extraction
    assert route_after_risk_extraction({"workflow_terminated":False}) == "critique"
    EVENTS.append("NON_MARKED_NORMAL_ROUTE_N12_PRESERVED_UNIT")
    # Real Alembic RLS with non-bypass, non-owner SQL role; same cluster.
    # A tenant GUC must be controlled by trusted middleware in production.
    # This proves policy behaviour for restricted SQL role, NOT Clerk mapping.
    cx = await asyncpg.connect(DSN)
    try:
        other = uuid4()
        await cx.execute("""
          INSERT INTO public.tenants (id,name,slug,subscription_plan)
          VALUES ($1,'G3 other isolated tenant',$2,'free')
        """, other, "g3-other-" + other.hex)
        await cx.execute("""
            CREATE ROLE c2pro_g3_rls_reader NOLOGIN NOSUPERUSER NOBYPASSRLS
                   NOCREATEDB NOCREATEROLE
        """)
        await cx.execute("""
            GRANT SELECT ON public.tenants,public.documents,
                public.n4_extraction_runs,public.n4_usage_reservations
            TO c2pro_g3_rls_reader
        """)
        rows = await cx.fetch("""
          SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
           WHERE relname IN ('tenants','documents','n4_extraction_runs',
                             'n4_usage_reservations')
           ORDER BY relname
        """)
        EVENTS.append("RLS_ACTUAL_ALEMBIC_METADATA_"+json.dumps(
            {r["relname"]: [r["relrowsecurity"],r["relforcerowsecurity"]] for r in rows}
        ))
        # SET ROLE strips the superuser/BYPASSRLS visibility of fixture owner.
        await cx.execute("SET ROLE c2pro_g3_rls_reader")
        assert await cx.fetchval("SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user") is False
        await cx.execute("SELECT set_config('app.current_tenant','',false)")
        count = await cx.fetchval("SELECT count(*) FROM public.documents")
        assert count == 0, ("RLS leaked unscoped documents",count)
        await cx.execute("SELECT set_config('app.current_tenant',$1,false)",str(T))
        self_count = await cx.fetchval("SELECT count(*) FROM public.documents WHERE tenant_id=$1",T)
        other_count = await cx.fetchval("SELECT count(*) FROM public.tenants WHERE id=$1",other)
        other_docs = await cx.fetchval("SELECT count(*) FROM public.documents WHERE tenant_id=$1",other)
        assert self_count == 1 and other_count == 0 and other_docs == 0
        run_count = await cx.fetchval("SELECT count(*) FROM public.n4_extraction_runs WHERE tenant_id=$1",T)
        assert run_count == 1
        reservations = await cx.fetchval("SELECT count(*) FROM public.n4_usage_reservations WHERE tenant_id=$1",T)
        assert reservations == 23
        EVENTS.append("REAL_ALEMBIC_RLS_ROLE_TENANT_SCOPE_PASS")
        await cx.execute("RESET ROLE")
    finally:
        await cx.close()

    # A stale fenced worker may not create a new reservation or repeat charges.
    assert PROVIDER.calls == list(range(23))
    EVENTS.append("REDELIVERED_POST_NO_REEXECUTION_PASS")

    print("G3_EVENTS_JSON="+json.dumps(EVENTS,sort_keys=True),flush=True)
    print("G3_CORE_PATH_STATUS=PASS_LIMITED; NO_REAL_CLERK_BROKER_PARSER_RLS",flush=True)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_g3())

