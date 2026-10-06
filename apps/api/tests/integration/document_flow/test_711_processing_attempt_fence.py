"""#711 stale-writer processing fence -- real PostgreSQL acceptance.

The canonical adversarial race, through the REAL production code paths
(ingestion ``_process``, analysis ``_run_document_analysis``, the recovery
sweep, reupload and the reprocess endpoint) on genuinely separate database
connections:

  1. A acquires processing authority at fencing_token N.
  2. A stalls before a real durable seam (its parser / graph is gated, and a
     frozen worker emits no heartbeat either).
  3. The PostgreSQL-clock lease expires (a short TTL, then real time passes;
     nothing is hand-seeded).
  4. B legitimately takes over at N+1 and completes.
  5. A resumes and reaches its real durable writes.
  6. A commits ZERO effects; only B's effects are canonical; replay and
     redelivery add nothing.

Only the edges that are not the subject are replaced: the storage read, the
file parser (to gate/pick content), the embedding provider and the broker.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core import processing_authority as pa
from src.core.tasks import document_recovery, ingestion_tasks
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag import rag_service as rag_service_module
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentStatus, DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application import project_snapshot_trigger

pytestmark = pytest.mark.asyncio


# ── harness ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _recovery_index_trigger(db: AsyncSession, test_user: Any):
    """Restore the migration-owned #711 discovery trigger.

    The integration bootstrap recreates ``public`` from ORM metadata after
    Alembic, which drops triggers; the system_recovery function/table survive
    (Migrations Check proves the migration creates them from scratch). Because
    system_recovery survives the per-test schema reset, this test's discovery
    rows are removed on teardown so no later recovery test scans them.
    """
    tenant_id = test_user.tenant_id
    await db.execute(
        text("DROP TRIGGER IF EXISTS trg_documents_recovery_index ON public.documents")
    )
    await db.execute(
        text(
            "CREATE TRIGGER trg_documents_recovery_index AFTER INSERT OR UPDATE "
            "ON public.documents FOR EACH ROW "
            "EXECUTE FUNCTION system_recovery.sync_document_work_index()"
        )
    )
    await db.commit()
    yield
    await db.rollback()
    await db.execute(
        text("DELETE FROM system_recovery.document_work_index WHERE tenant_id = :t"),
        {"t": tenant_id},
    )
    await db.commit()


def _dsn(db: AsyncSession) -> str:
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


class _GatedParser:
    """Gives each worker its own content; can freeze a named worker mid-run."""

    def __init__(self) -> None:
        self._queue: list[str] = []
        self.entered: dict[str, asyncio.Event] = {}
        self.release: dict[str, asyncio.Event] = {}
        self.payloads: dict[str, dict[str, Any]] = {}

    def expect(self, name: str, marker: str, *, gated: bool = False) -> None:
        self._queue.append(name)
        self.payloads[name] = _payload(marker)
        self.entered[name] = asyncio.Event()
        if gated:
            self.release[name] = asyncio.Event()

    async def parse_document_file(self, _document: Any, _path: Any) -> dict[str, Any]:
        name = self._queue.pop(0)
        self.entered[name].set()
        if name in self.release:
            await self.release[name].wait()
        return self.payloads[name]


def _payload(marker: str) -> dict[str, Any]:
    body = (
        f"Clause 1 {marker}: the contractor shall deliver the {marker} works "
        f"within the agreed schedule. Contact {marker}@example.com for notices.\n\n"
        f"Clause 2 {marker}: a delay penalty of one percent per week applies to "
        f"the {marker} milestone until practical completion."
    )
    return {"text_blocks": [{"text": body, "page": 1}]}


@pytest.fixture
async def worker(db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Workers on their own engine/connections; only non-subject edges faked."""
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def raw_session():
        async with maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def tenant_session(tenant_id):
        async with maker() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)}
            )
            yield session
            await session.commit()

    async def _no_init() -> None:
        return None

    storage = LocalFileStorageService(base_dir=tmp_path)
    parser = _GatedParser()
    triggered: list[dict[str, Any]] = []

    class _Trigger:
        def __init__(self, **_: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> dict[str, Any]:
            triggered.append(kwargs)
            return {"task_id": None, "task_name": "fake", "queue": "document_parsing"}

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1)] * 1536 for i, _ in enumerate(texts)]

    async def _no_heartbeat(**_: Any) -> None:
        # A stalled worker is frozen: it emits no heartbeat either.
        await asyncio.Event().wait()

    monkeypatch.setattr(ingestion_tasks, "get_raw_session", raw_session)
    monkeypatch.setattr(ingestion_tasks, "init_db", _no_init)
    monkeypatch.setattr(ingestion_tasks, "build_storage_service", lambda: storage)
    monkeypatch.setattr(ingestion_tasks.file_parser, "parse_document_file", parser.parse_document_file)
    monkeypatch.setattr(ingestion_tasks, "TriggerDocumentAnalysisUseCase", _Trigger)
    monkeypatch.setattr(ingestion_tasks, "_document_processing_heartbeat_loop", _no_heartbeat)
    monkeypatch.setattr(rag_service_module, "_embed_texts", _fake_embed)
    monkeypatch.setattr(project_snapshot_trigger, "get_session_with_tenant", tenant_session)
    monkeypatch.setattr(project_snapshot_trigger, "enqueue_project_snapshot", lambda **_: None)
    for module in ("upload_document_use_case", "reupload_document_use_case"):
        monkeypatch.setattr(
            f"src.documents.application.{module}.enqueue_project_snapshot", lambda **_: None
        )
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case._enqueue_document_processing",
        lambda *_args, **_kwargs: None,
    )

    class _Worker:
        pass

    w = _Worker()
    w.maker = maker
    w.raw_session = raw_session
    w.tenant_session = tenant_session
    w.storage = storage
    w.parser = parser
    w.triggered = triggered
    try:
        yield w
    finally:
        # A failed assertion must not leave a gated worker holding a
        # transaction open across the per-test schema reset.
        for gate in parser.release.values():
            gate.set()
        await asyncio.sleep(0.5)
        await engine.dispose()


async def _upload(db: AsyncSession, worker: Any, test_user: Any) -> tuple[Any, Any]:
    project_id = uuid4()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
            "created_at, updated_at) VALUES (:id, :tid, 'p711', :code, 'construction', "
            "'active', 'EUR', now(), now())"
        ),
        {"id": project_id, "tid": test_user.tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    document = await UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=worker.storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=revisions,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"%PDF contract v1")),
        document_type=DocumentType.CONTRACT,
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
    )
    [revision] = await revisions.list_lineage(document.id, test_user.tenant_id)
    return document, revision


async def _reupload(db: AsyncSession, worker: Any, test_user: Any, document: Any) -> Any:
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    await ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        revision_repository=revisions,
        storage_service=worker.storage,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        tenant_id=test_user.tenant_id,
        document_id=document.id,
        file_content=b"%PDF contract v2",
        user_id=test_user.id,
    )
    return (await revisions.list_lineage(document.id, test_user.tenant_id))[-1]


async def _op(db: AsyncSession, document_id: UUID) -> Any:
    # READ COMMITTED: every statement sees the latest committed state; no
    # rollback (which would expire the test's ORM fixtures mid-test).
    return (
        await db.execute(
            text("SELECT * FROM document_processing_operations WHERE document_id = :d"),
            {"d": document_id},
        )
    ).first()


async def _effects(db: AsyncSession, document_id: UUID, project_id: UUID) -> dict[str, Any]:
    """Every canonical durable effect ingestion can produce for this document."""
    one = lambda sql: db.execute(text(sql), {"d": document_id, "p": project_id})  # noqa: E731
    document = (
        await one(
            "SELECT upload_status::text AS status, parsing_error, document_metadata "
            "FROM documents WHERE id = :d"
        )
    ).one()
    return {
        "status": document.status,
        "parsing_error": document.parsing_error,
        "parsed_text": (document.document_metadata or {}).get("parsed_text", ""),
        "metadata": dict(document.document_metadata or {}),
        "clauses": [r.full_text for r in (await one(
            "SELECT full_text FROM clauses WHERE document_id = :d ORDER BY clause_code"
        )).all()],
        "stakeholders": sorted(r.email for r in (await one(
            "SELECT email FROM stakeholders WHERE project_id = :p"
        )).all()),
        "chunks": [r.content for r in (await one(
            "SELECT content FROM document_chunks WHERE document_id = :d"
        )).all()],
        "events": sorted(r.event_type for r in (await one(
            "SELECT event_type FROM project_events WHERE project_id = :p"
        )).all()),
    }


def _only(effects: dict[str, Any], winner: str, loser: str) -> None:
    blob = repr(
        {k: effects[k] for k in ("parsed_text", "clauses", "stakeholders", "chunks", "metadata")}
    )
    assert loser not in blob, f"stale worker {loser!r} leaked a durable effect: {blob}"
    assert winner in effects["parsed_text"]
    assert effects["clauses"] and all(winner in c for c in effects["clauses"])
    assert effects["stakeholders"] == [f"{winner}@example.com"]
    assert effects["chunks"] and all(winner in c for c in effects["chunks"])
    assert effects["status"] == "parsed_pending_analysis"
    assert effects["parsing_error"] is None


async def _expire_lease() -> None:
    """Let real PostgreSQL time pass beyond a 1s lease."""
    await asyncio.sleep(1.4)


# ── canonical adversarial race ───────────────────────────────────────────────


async def test_stale_owner_commits_zero_effects_after_takeover(
    db: AsyncSession, test_user: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """STALE_DURABLE_WRITE_REJECTED + EXPIRED_OWNER_TAKEOVER + FENCE_MONOTONIC
    + DUPLICATE_REDELIVERY_IDEMPOTENT through the real ingestion seams."""
    document, revision = await _upload(db, worker, test_user)
    worker.parser.expect("A", "alpha", gated=True)
    worker.parser.expect("B", "beta")

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    worker_a = asyncio.create_task(ingestion_tasks._process(document.id, revision.revision_id))
    await asyncio.wait_for(worker.parser.entered["A"].wait(), 10)
    fence_a = int((await _op(db, document.id)).fencing_token)
    await _expire_lease()

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    result_b = await ingestion_tasks._process(document.id, revision.revision_id)
    assert result_b["status"] == "success"
    op_b = await _op(db, document.id)
    assert int(op_b.fencing_token) == fence_a + 1, "takeover increments the fence"
    assert op_b.stage == "ANALYSIS" and op_b.phase == "PENDING"

    worker.parser.release["A"].set()
    result_a = await asyncio.wait_for(worker_a, 20)
    assert result_a["status"] == "authority_lost"

    effects = await _effects(db, document.id, document.project_id)
    _only(effects, "beta", "alpha")
    assert effects["events"].count("revision.analyzed") == 1
    assert len(worker.triggered) == 1, "only the owner hands over to analysis"
    assert int((await _op(db, document.id)).fencing_token) == fence_a + 1

    # Replay / redelivery of the completed ingestion adds nothing.
    replay = await ingestion_tasks._process(document.id, revision.revision_id)
    assert replay["status"] in {"already_ingested", "completed"}
    assert await _effects(db, document.id, document.project_id) == effects
    assert len(worker.triggered) == 1


async def test_active_owner_is_never_recovered_or_stolen(
    db: AsyncSession, test_user: Any, worker: Any
) -> None:
    """ACTIVE_WORK_NOT_RECOVERED: a valid DB lease wins over a stale index hint
    and over a second invocation that merely started."""
    document, revision = await _upload(db, worker, test_user)
    worker.parser.expect("A", "alpha", gated=True)
    worker_a = asyncio.create_task(ingestion_tasks._process(document.id, revision.revision_id))
    await asyncio.wait_for(worker.parser.entered["A"].wait(), 10)
    fence_a = int((await _op(db, document.id)).fencing_token)

    # A duplicate delivery while A is alive must not acquire.
    duplicate = await ingestion_tasks._process(document.id, revision.revision_id)
    assert duplicate["status"] == "busy"

    # Make the discovery index look abandoned; the DB lease still says active.
    await db.execute(
        text(
            "UPDATE system_recovery.document_work_index SET heartbeat_at = :old, "
            "updated_at = :old WHERE document_id = :d"
        ),
        {"d": document.id, "old": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)},
    )
    await db.commit()
    dispatched: list[Any] = []

    class _Task:
        def apply_async(self, **kwargs: Any) -> None:
            dispatched.append(kwargs)

    sweep = await document_recovery._sweep_async(
        stale_after_seconds=60,
        session_factory=_sweep_sessions(worker),
        ingestion_task=_Task(),
        analysis_task=_Task(),
    )
    assert dispatched == [], sweep
    assert int((await _op(db, document.id)).fencing_token) == fence_a

    worker.parser.release["A"].set()
    assert (await asyncio.wait_for(worker_a, 20))["status"] == "success"


class _NoBroker:
    def apply_async(self, **_: Any) -> None:
        return None


def _sweep_sessions(worker: Any) -> Any:
    @asynccontextmanager
    async def factory(tenant_id):
        async with worker.maker() as session:
            if tenant_id is not None:
                await session.execute(
                    text("SELECT set_config('app.current_tenant', :t, true)"),
                    {"t": str(tenant_id)},
                )
            yield session
            await session.commit()

    return factory


async def test_crash_window_recovery_hands_exact_authority_to_one_replacement(
    db: AsyncSession, test_user: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CRASH_WINDOW_RECOVERY + DUPLICATE_REDELIVERY_IDEMPOTENT: the sweep claims
    N+1 only after the DB lease expired and passes that exact authority; a
    redelivered copy of the recovery message cannot adopt it twice."""
    document, revision = await _upload(db, worker, test_user)
    worker.parser.expect("A", "alpha", gated=True)
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    worker_a = asyncio.create_task(ingestion_tasks._process(document.id, revision.revision_id))
    await asyncio.wait_for(worker.parser.entered["A"].wait(), 10)
    fence_a = int((await _op(db, document.id)).fencing_token)
    await _expire_lease()
    await db.execute(
        text(
            "UPDATE system_recovery.document_work_index SET heartbeat_at = :old, "
            "updated_at = :old WHERE document_id = :d"
        ),
        {"d": document.id, "old": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)},
    )
    await db.commit()

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    dispatched: list[dict[str, Any]] = []

    class _Task:
        def apply_async(self, **kwargs: Any) -> None:
            dispatched.append(kwargs)

    await document_recovery._sweep_async(
        stale_after_seconds=60,
        session_factory=_sweep_sessions(worker),
        ingestion_task=_Task(),
        analysis_task=_Task(),
    )
    [message] = dispatched
    claimed = message["kwargs"]["authority"]
    assert claimed["fencing_token"] == fence_a + 1
    assert (await _op(db, document.id)).phase == "CLAIMED"

    worker.parser.expect("B", "beta")
    kwargs = message["kwargs"]
    result_b = await ingestion_tasks._process(
        UUID(kwargs["document_id"]),
        UUID(kwargs["revision_id"]) if kwargs["revision_id"] else None,
        authority=kwargs["authority"],
    )
    assert result_b["status"] == "success"

    redelivered = await ingestion_tasks._process(
        UUID(kwargs["document_id"]),
        UUID(kwargs["revision_id"]) if kwargs["revision_id"] else None,
        authority=kwargs["authority"],
    )
    assert redelivered["status"] in {"already_ingested", "authority_lost", "busy"}

    worker.parser.release["A"].set()
    assert (await asyncio.wait_for(worker_a, 20))["status"] == "authority_lost"
    effects = await _effects(db, document.id, document.project_id)
    _only(effects, "beta", "alpha")
    assert len(worker.triggered) == 1


async def test_new_revision_supersedes_a_live_owner(
    db: AsyncSession, test_user: Any, worker: Any
) -> None:
    """REVISION_SUPERSESSION_FENCED: a new canonical revision invalidates the
    previous writer even while its lease is still valid."""
    document, revision_1 = await _upload(db, worker, test_user)
    worker.parser.expect("A", "alpha", gated=True)
    worker_a = asyncio.create_task(ingestion_tasks._process(document.id, revision_1.revision_id))
    await asyncio.wait_for(worker.parser.entered["A"].wait(), 10)
    op_a = await _op(db, document.id)

    revision_2 = await _reupload(db, worker, test_user, document)
    op_2 = await _op(db, document.id)
    assert int(op_2.generation) == int(op_a.generation) + 1
    assert int(op_2.fencing_token) > int(op_a.fencing_token)
    assert op_2.revision_id == revision_2.revision_id

    worker.parser.expect("B", "beta")
    result_b = await ingestion_tasks._process(document.id, revision_2.revision_id)
    assert result_b["status"] == "success"

    worker.parser.release["A"].set()
    assert (await asyncio.wait_for(worker_a, 20))["status"] == "authority_lost"
    effects = await _effects(db, document.id, document.project_id)
    _only(effects, "beta", "alpha")

    # A late message pinned to the superseded revision is refused and adds nothing.
    late = await ingestion_tasks._process(document.id, revision_1.revision_id)
    assert late["status"] in {"superseded", "already_ingested"}
    assert await _effects(db, document.id, document.project_id) == effects


async def test_reprocess_generation_isolates_metadata_and_failure_path(
    db: AsyncSession, test_user: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GENERATION_METADATA_ISOLATION + stale failure path: after the sweep fails
    the abandoned generation and the user reprocesses, the old worker can
    neither write metadata/outputs nor mark anything ERROR."""
    from src.documents.adapters.http import router as documents_router

    document, _revision = await _upload(db, worker, test_user)
    version = (
        await db.execute(text("SELECT version FROM documents WHERE id = :d"), {"d": document.id})
    ).scalar_one()
    await db.execute(
        text(
            "UPDATE documents SET document_metadata = CAST(:m AS jsonb) WHERE id = :d"
        ),
        {
            "d": document.id,
            "m": json.dumps(
                {
                    "processing_recovery": {
                        "stage": DocumentStatus.PARSING.value,
                        "generation": document_recovery._generation(
                            version=int(version), revision_id=_revision.revision_id
                        ),
                        "attempts": document_recovery.MAX_RECOVERY_ATTEMPTS,
                        "outcome": "requeue_ingestion",
                    }
                }
            ),
        },
    )
    await db.commit()

    worker.parser.expect("A", "alpha", gated=True)
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    worker_a = asyncio.create_task(ingestion_tasks._process(document.id, None))
    await asyncio.wait_for(worker.parser.entered["A"].wait(), 10)
    op_a = await _op(db, document.id)
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    await db.execute(
        text(
            "UPDATE system_recovery.document_work_index SET heartbeat_at = :old, "
            "updated_at = :old WHERE document_id = :d"
        ),
        {"d": document.id, "old": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)},
    )
    await db.commit()

    sweep = await document_recovery._sweep_async(
        stale_after_seconds=60,
        session_factory=_sweep_sessions(worker),
        ingestion_task=_NoBroker(),
        analysis_task=_NoBroker(),
    )
    assert sweep["failed_retryable"] == 1, sweep
    assert (await _effects(db, document.id, document.project_id))["status"] == "error"

    enqueued: list[dict[str, Any]] = []
    monkeypatch.setattr(
        documents_router,
        "_enqueue_document_processing",
        lambda document_id, revision_id=None, generation=None: enqueued.append(
            {"generation": generation}
        ) or "task-1",
    )

    async with worker.tenant_session(test_user.tenant_id) as session:
        repo = SqlAlchemyDocumentRepository(session)

        async def _no_reviews(_tenant, _ids):
            return {}

        await documents_router.reprocess_document_endpoint(
            project_id=document.project_id,
            document_id=document.id,
            user_id=test_user.id,
            tenant_id=test_user.tenant_id,
            repo=repo,
            pending_review_lookup=_no_reviews,
        )
    op_2 = await _op(db, document.id)
    assert int(op_2.generation) == int(op_a.generation) + 1
    assert enqueued == [{"generation": int(op_2.generation)}]

    worker.parser.expect("B", "beta")
    result_b = await ingestion_tasks._process(document.id, None, generation=int(op_2.generation))
    assert result_b["status"] == "success"

    worker.parser.release["A"].set()
    assert (await asyncio.wait_for(worker_a, 20))["status"] == "authority_lost"
    effects = await _effects(db, document.id, document.project_id)
    _only(effects, "beta", "alpha")
    assert "processing_recovery" not in effects["metadata"], "old generation's budget is gone"


# ── authority primitives against PostgreSQL ──────────────────────────────────


async def _seed_plain(db: AsyncSession, test_user: Any, worker: Any) -> Any:
    document, _revision = await _upload(db, worker, test_user)
    return document


async def test_bounded_reprocess_generation_rejects_stale_revision_before_mutation(
    db: AsyncSession, test_user: Any, worker: Any
) -> None:
    """#686: expected revision is a transactional CAS on processing authority."""
    document, revision = await _upload(db, worker, test_user)
    tenant = test_user.tenant_id

    await db.execute(
        text(
            "UPDATE documents SET upload_status = 'error', parsing_error = 'fixture' "
            "WHERE id = :d AND tenant_id = :t"
        ),
        {"d": document.id, "t": tenant},
    )
    await db.commit()

    before = await _op(db, document.id)
    assert before.revision_id == revision.revision_id
    before_generation = int(before.generation)
    stale_revision_id = uuid4()

    with pytest.raises(pa.ProcessingAuthorityLost):
        async with worker.tenant_session(tenant) as session:
            await pa.begin_generation(
                session,
                tenant_id=tenant,
                document_id=document.id,
                revision_id=None,
                expected_revision_id=stale_revision_id,
            )

    after_refusal = await _op(db, document.id)
    assert int(after_refusal.generation) == before_generation
    assert after_refusal.revision_id == revision.revision_id
    status_after_refusal = (
        await db.execute(
            text(
                "SELECT upload_status::text FROM documents "
                "WHERE id = :d AND tenant_id = :t"
            ),
            {"d": document.id, "t": tenant},
        )
    ).scalar_one()
    assert status_after_refusal == "error"

    async with worker.tenant_session(tenant) as session:
        generation = await pa.begin_generation(
            session,
            tenant_id=tenant,
            document_id=document.id,
            revision_id=None,
            expected_revision_id=revision.revision_id,
        )

    after_success = await _op(db, document.id)
    assert generation == before_generation + 1
    assert int(after_success.generation) == generation
    assert after_success.revision_id == revision.revision_id


async def test_fence_is_monotonic_and_takeover_requires_expired_db_lease(
    db: AsyncSession, test_user: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EXPIRED_OWNER_TAKEOVER + FENCE_MONOTONIC + STALE_HEARTBEAT_REJECTED."""
    document = await _seed_plain(db, test_user, worker)
    tenant = test_user.tenant_id
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)

    async with worker.tenant_session(tenant) as s:
        first = await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.INGESTION
        )
    a = first.authority
    assert a is not None

    async with worker.tenant_session(tenant) as s:
        busy = await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.INGESTION
        )
    assert busy.outcome is pa.AcquireOutcome.BUSY, "never steal a valid owner"

    await _expire_lease()
    async with worker.tenant_session(tenant) as s:
        assert await pa.heartbeat(s, a) is False, "an expired owner cannot renew"
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    async with worker.tenant_session(tenant) as s:
        taken = await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.INGESTION
        )
    b = taken.authority
    assert b is not None
    assert b.fencing_token == a.fencing_token + 1
    assert b.attempt_id != a.attempt_id and b.owner_token != a.owner_token

    lease_before = (await _op(db, document.id)).lease_expires_at
    async with worker.tenant_session(tenant) as s:
        assert await pa.heartbeat(s, a) is False, "a superseded owner cannot renew"
    assert (await _op(db, document.id)).lease_expires_at == lease_before
    async with worker.tenant_session(tenant) as s:
        assert await pa.heartbeat(s, b) is True
    with pytest.raises(pa.ProcessingAuthorityLost):
        async with worker.tenant_session(tenant) as s:
            await pa.verify_in_transaction(s, a)
    async with worker.tenant_session(tenant) as s:
        await pa.verify_in_transaction(s, b)


async def test_graph_seams_fence_through_the_bound_authority(
    db: AsyncSession, test_user: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Analysis-stage race: a stale analysis worker's graph seam (graph.completed
    event) and terminal status write are both rejected; B's are canonical."""
    document = await _seed_plain(db, test_user, worker)
    tenant = test_user.tenant_id
    await db.execute(
        text(
            "UPDATE documents SET upload_status = 'parsed_pending_analysis', "
            "document_metadata = CAST(:m AS jsonb) WHERE id = :d"
        ),
        {"d": document.id, "m": '{"parsed_text": "Clause text for analysis."}'},
    )
    await db.execute(
        text(
            "INSERT INTO document_chunks (id, tenant_id, document_id, project_id, content, "
            "embedding, metadata) VALUES (:id, :t, :d, :p, 'chunk', CAST(:e AS vector), '{}')"
        ),
        {
            "id": uuid4(), "t": tenant, "d": document.id, "p": document.project_id,
            "e": "[" + ",".join(["0.001"] * 1536) + "]",
        },
    )
    await db.commit()

    a_entered, a_release = asyncio.Event(), asyncio.Event()

    class _Graph:
        def __init__(self, name: str) -> None:
            self.name = name

        async def run(self, state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
            if self.name == "A":
                a_entered.set()
                await a_release.wait()
            await project_snapshot_trigger.record_project_event_and_enqueue_snapshot(
                project_id=UUID(state["project_id"]),
                tenant_id=UUID(state["tenant_id"]),
                event_type="graph.completed",
                payload={"worker": self.name},
                trigger=project_snapshot_trigger.SnapshotTrigger.GRAPH_COMPLETED,
            )
            return {"analysis_id": str(uuid4()), "human_approval_required": False}

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    worker_a = asyncio.create_task(
        ingestion_tasks._run_document_analysis(
            tenant_id=tenant, document_id=document.id, orchestrator=_Graph("A")
        )
    )
    await asyncio.wait_for(a_entered.wait(), 10)
    fence_a = int((await _op(db, document.id)).fencing_token)
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)

    result_b = await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=_Graph("B")
    )
    assert result_b["status"] == "completed"
    op_b = await _op(db, document.id)
    assert int(op_b.fencing_token) == fence_a + 1 and op_b.phase == "COMPLETED"

    a_release.set()
    result_a = await asyncio.wait_for(worker_a, 20)
    assert result_a["status"] == "authority_lost"

    payloads = (
        await db.execute(
            text(
                "SELECT payload FROM project_events WHERE project_id = :p "
                "AND event_type = 'graph.completed'"
            ),
            {"p": document.project_id},
        )
    ).scalars().all()
    assert [p["worker"] for p in payloads] == ["B"], "the stale graph seam wrote nothing"
    effects = await _effects(db, document.id, document.project_id)
    assert effects["status"] == "analyzed"
    assert "analysis_last_attempt_incomplete" not in effects["metadata"]


async def test_superseded_heartbeat_loop_stops_and_refreshes_nothing(
    db: AsyncSession, test_user: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """STALE_HEARTBEAT_REJECTED through the real heartbeat loop: once B owns
    the document, A's loop stops; neither B's lease nor the discovery hint
    moves because of A."""
    document = await _seed_plain(db, test_user, worker)
    tenant = test_user.tenant_id
    frozen_loop = ingestion_tasks._document_processing_heartbeat_loop
    monkeypatch.undo()  # this test drives the REAL heartbeat loop
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", worker.raw_session)
    loop = ingestion_tasks._document_processing_heartbeat_loop
    assert loop is not frozen_loop

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    async with worker.tenant_session(tenant) as s:
        a = (await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.INGESTION
        )).authority
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    async with worker.tenant_session(tenant) as s:
        b = (await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.INGESTION
        )).authority
    assert a is not None and b is not None
    before = await _op(db, document.id)
    hint_before = (
        await db.execute(
            text("SELECT heartbeat_at FROM system_recovery.document_work_index WHERE document_id = :d"),
            {"d": document.id},
        )
    ).scalar_one()

    await asyncio.wait_for(loop(authority=a, interval_seconds=0.05), 5)

    after = await _op(db, document.id)
    assert (after.lease_expires_at, after.heartbeat_at, after.fencing_token) == (
        before.lease_expires_at, before.heartbeat_at, before.fencing_token,
    )
    hint_after = (
        await db.execute(
            text("SELECT heartbeat_at FROM system_recovery.document_work_index WHERE document_id = :d"),
            {"d": document.id},
        )
    ).scalar_one()
    assert hint_after == hint_before, "a superseded worker must not keep the discovery hint fresh"
