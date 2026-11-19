"""G4 isolated Celery worker: real broker, process-separated, stub N1/N2/provider.

Import through: celery -A g4_worker_app:app worker -P solo -Q document_parsing.
Never uses external model or production database; service URLs validated by shell.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(os.environ["G4_RUN_DIR"])
CTX = json.loads((ROOT / "context.json").read_text())
for key, value in CTX["scope_env"].items():
    os.environ[key] = value

from src.core.tasks.celery_app import celery_app as app
from src.core.tasks import ingestion_tasks as tasks
from src.core.processing_authority import (
    ProcessingAuthority, ProcessingStage, acquire, adopt, finish_ingestion,
    AcquireOutcome, bound_authority,
)
from src.analysis.application import n4_only_pilot as graph
from src.analysis.application.n4_incremental_runner import N4IncrementalRunner
from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotScope, pilot_marker,
)
from src.analysis.adapters.graph import nodes as normal_nodes
from src.analysis.adapters.graph import nodes_extended as extended_nodes
from src.analysis.application.critique_extraction_use_case import CritiqueExtractionUseCase
from src.analysis.application.structured_source_trust import DecideStructuredSourceTrustService
from src.analysis.application import persist_resume_analysis, document_artifact_completion
from src.core.tasks import materialization_tasks
from tests.integration.analysis.test_n4_window_runner_pg import StubProvider

DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
BROKER = os.environ["CELERY_BROKER_URL"]
assert BROKER.startswith("redis://127.0.0.1:") and DB_URL.startswith("postgresql+asyncpg://aigenadmin:@127.0.0.1:")
assert os.environ.get("G4_ALLOW_BILLABLE") is None
app.conf.update(
    broker_url=BROKER, result_backend=os.environ["CELERY_RESULT_BACKEND_URL"],
    task_always_eager=False, worker_prefetch_multiplier=1,
    broker_transport_options={"socket_connect_timeout": 1, "socket_timeout": 4},
    task_default_queue="document_parsing", beat_schedule={},
)
PROVIDER = StubProvider()
T, D, R, P = (UUID(CTX[k]) for k in ("tenant_id", "document_id", "revision_id", "project_id"))
SOURCE = CTX["text"]

def event(name: str, **extra: object) -> None:
    record = {"event": name, "pid": os.getpid(), **extra}
    with (ROOT / "worker_events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def forbidden(label: str):
    def stop(*args, **kwargs):
        event("FORBIDDEN_SIDE_EFFECT", label=label)
        raise AssertionError("FORBIDDEN_" + label)
    return stop


async def ingestion_stub(*, document_id, revision_id, generation, authority):
    assert document_id == D and revision_id == R and generation == 3
    grant = ProcessingAuthority.from_message(authority)
    assert grant is not None and grant.generation == 3 and grant.stage is ProcessingStage.INGESTION
    engine = create_async_engine(DB_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            async with session.begin():
                accepted = await adopt(session, grant)
                if not accepted:
                    event("DUPLICATE_ADOPT_DENIED", fencing_token=grant.fencing_token)
                    return {"status": "duplicate_denied", "generation": 3}
                event("CELERY_WORKER_ADOPT_ONCE", fencing_token=grant.fencing_token)
                await finish_ingestion(session, grant)
        result = tasks.process_document_n4_only_pilot_async.apply_async(
            kwargs={"tenant_id": str(T), "document_id": str(D), "generation": 3},
            queue="document_parsing",
        )
        event("ANALYSIS_ENQUEUED_REAL_BROKER", task_id=result.id)
        return {"status": "parsed", "analysis_id": result.id}
    finally:
        await engine.dispose()


async def analysis_stub(*, tenant_id, document_id, generation, n4_only_pilot=False, **kwargs):
    assert UUID(str(tenant_id)) == T and document_id == D
    assert generation == 3 and n4_only_pilot is True
    engine = create_async_engine(DB_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            async with session.begin():
                acquired = await acquire(
                    session, tenant_id=T, document_id=D, revision_id=R,
                    generation=3, stage=ProcessingStage.ANALYSIS,
                )
                assert acquired.outcome is AcquireOutcome.ACQUIRED, acquired
                a = acquired.authority
        event("ANALYSIS_FENCE_ACQUIRED", fence=a.fencing_token)
        scope = N4OnlyPilotScope.from_environment()
        async def n1(state):
            event("N1_PARSER_STUB")
            return {"document_text": SOURCE}
        async def n2(state):
            event("N2_PII_STUB")
            return {"anonymized_text": SOURCE}
        async def n4(state):
            event("REAL_GOVERNED_N4_RUNNER")
            graph.attest_n4_pilot_input(state)
            runner = N4IncrementalRunner(
                session_factory=factory, provider=PROVIDER,
                enabled=True, run_cap_usd=Decimal("5"),
                per_window_reservation_usd=Decimal("0.50"), period_key="2026-11",
                max_context_chars=600, overlap_chars=50,
            )
            result = await runner.run(
                authority=a, project_id=P, model_safe_text=SOURCE,
                n2_projection_attested=True,
            )
            assert result.status == "COMPLETE" and result.total_windows == 23
            assert result.examined_windows == 23 and result.settled_receipt_windows == 23
            event("N4_23_SETTLED", provider_calls=len(PROVIDER.calls))
            return {
                "n4_incremental_run_id": str(result.run_id),
                "n4_incremental_window_coverage": {"examined": 23, "total": 23},
                "extracted_risks": [{"title": "Synthetic finding"}],
            }
        def identity(state):
            return (a, P, SOURCE)
        def limits():
            return (Decimal("5"), Decimal("0.50"), 600, 50)
        state = {
            "tenant_id": str(T), "project_id": str(P), "document_id": str(D),
            "document_revision_id": str(R), "doc_type": "contract",
            "document_text": SOURCE, "messages": [], "extracted_risks": [],
            "n4_only_pilot": pilot_marker(scope),
        }
        with ExitStack() as stack:
            for obj, attr, name in (
                (normal_nodes, "critique_node", "N12_GRAPH"),
                (CritiqueExtractionUseCase, "execute", "N12_SERVICE"),
                (normal_nodes, "human_interrupt_node", "HITL_GRAPH"),
                (extended_nodes, "coherence_scorer_node", "SCORE_GRAPH"),
                (DecideStructuredSourceTrustService, "execute", "TRUST_DECISION"),
                (persist_resume_analysis, "persist_resume_analysis_atomically", "TRUST_COMMIT"),
                (document_artifact_completion, "persist_artifact_and_enqueue_project_graph", "TRUST_MATERIALIZE"),
                (materialization_tasks, "enqueue_materialization", "TRUST_DISPATCH"),
            ):
                stack.enter_context(patch.object(obj, attr, forbidden(name)))
            for obj, attr, value in (
                (graph, "document_ingestion_node", n1),
                (graph, "pii_anonymizer_node", n2),
                (graph, "n4_only_risk_node", n4),
                (graph, "_identity", identity),
                (graph, "_limits", limits),
            ):
                stack.enter_context(patch.object(obj, attr, value))
            assert set(graph.build_n4_only_workflow().nodes) == {
                "document_ingestion", "pii_anonymizer", "risk_extractor"
            }
            event("FAIL_FAST_SIDE_EFFECT_SPIES_ARMED")
            with bound_authority(a):
                result = await graph.run_n4_only_pilot(state)
            assert result["n12_status"] == "UNASSESSED"
            assert result["coherence_score"] is None
            assert result["trust_state"] == "PROPOSED"
            assert result["hitl_generated"] is False
        # Only because lifecycle/parser are stubs: synthesize same local GET marker.
        async with factory() as session:
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
        event("N4_COMPLETED_REAL_WORKER", provider_calls=len(PROVIDER.calls))
        return {"status": result["n4_only_pilot_status"], "windows": 23}
    finally:
        await engine.dispose()


tasks._run_document_processing_task_lifecycle = ingestion_stub
tasks._run_document_analysis_task_lifecycle = analysis_stub
event("WORKER_ENTRYPOINT_READY", broker=BROKER)
