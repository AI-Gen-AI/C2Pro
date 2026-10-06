"""#852 -- SCHEDULE ingestion must not mutate the canonical WBS.

TS-INT-852-SCHEDULE-WBS-GOVERNANCE-001. REAL PostgreSQL, a REAL ``.xlsx`` schedule
uploaded through the real upload / reupload use cases, the REAL ingestion worker
``_process`` (real composite / Excel parser, real entity extraction, real RAG
ingestion, real #711 processing authority) and the REAL documents parse endpoint
wiring (``get_entity_extraction_service`` + ``ParseDocumentUseCase``). Only the
non-subject edges are replaced: object storage (local), embeddings, the broker.

A schedule ACTIVITY is not a WBS NODE, and a schedule's visible ``wbs`` code is not
a canonical WBS identity. Until the governed WBS baseline authority exists
(PC-1 / PC-2) and Schedule Temporal Intelligence models activities, ingestion only
observes a schedule:

* the canonical ``wbs_nodes`` table is byte-identical -- no first WBS is created,
  an existing WBS is neither augmented nor replaced nor renumbered, a reparse
  deletes nothing (not even nodes a pre-#852 parse produced, nor the human
  children / manually verified RACI / BOM links beneath them);
* the schedule stays recoverable: the immutable revision is re-fetchable
  (hash-verified) and deterministically reparsable, its rows are in the RAG
  chunks (worker) and ``parsed_text`` (parse endpoint), and the document reaches
  ``PARSED_PENDING_ANALYSIS``;
* other projects and tenants are untouched.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import openpyxl
import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.coherence.schedule_clause_builder import build_schedule_clauses
from src.core.auth.models import SubscriptionPlan, Tenant
from src.core.tasks import ingestion_tasks
from src.documents.adapters.http.router import get_entity_extraction_service
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag import rag_service as rag_service_module
from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
    SqlAlchemyRagIngestionService,
)
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.document_source import fetch_source_file
from src.documents.application.parse_document_use_case import ParseDocumentUseCase
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Document, DocumentType
from src.procurement.adapters.persistence.models import BOMItemORM
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application import project_snapshot_trigger
from tests.support.legacy_wbs import seed_legacy_from_dicts

pytestmark = pytest.mark.asyncio

HEADERS = ["WBS", "Task", "Start Date", "End Date", "Duration", "Predecessors"]
# Visible codes that do NOT collide with the human WBS below ("1" / "1.1"): a
# schedule must not ADD canonical nodes either, not only "not overwrite" them.
SCHEDULE_V1 = [
    ["2", "Mobilisation", datetime(2026, 1, 5), datetime(2026, 1, 16), 10, None],
    ["2.1", "Excavation", datetime(2026, 1, 19), datetime(2026, 2, 13), 20, "2"],
    [None, "Topping out", datetime(2026, 3, 2), datetime(2026, 3, 6), 5, "2.1"],
]
SCHEDULE_V2 = [
    ["2", "Mobilisation", datetime(2026, 1, 5), datetime(2026, 1, 23), 15, None],
    ["2.1", "Excavation (resequenced)", datetime(2026, 1, 26), datetime(2026, 2, 20), 20, "2"],
]


def _xlsx(rows: list[list[Any]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ── harness: the real worker on its own connections ──────────────────────────


def _dsn(db: AsyncSession) -> str:
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


async def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.001 * (i + 1)] * 1536 for i, _ in enumerate(texts)]


@pytest.fixture
async def worker(db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    engine = create_async_engine(_dsn(db), pool_size=5, max_overflow=5)
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

    async def _no_heartbeat(**_: Any) -> None:
        return None

    class _Trigger:
        def __init__(self, **_: Any) -> None:
            pass

        async def execute(self, **_: Any) -> dict[str, Any]:
            return {"task_id": None, "task_name": "fake", "queue": "document_parsing"}

    storage = LocalFileStorageService(base_dir=tmp_path)
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", raw_session)
    monkeypatch.setattr(ingestion_tasks, "init_db", _no_init)
    monkeypatch.setattr(ingestion_tasks, "build_storage_service", lambda: storage)
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
    try:
        yield storage
    finally:
        await engine.dispose()


async def _project(db: AsyncSession, tenant_id: UUID) -> UUID:
    if await db.get(Tenant, tenant_id) is None:
        db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                      subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0))
        await db.commit()
    project_id = uuid4()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
             "created_at, updated_at) VALUES (:id, :tid, 'p852', :code, 'construction', "
             "'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return project_id


async def _upload_schedule(
    db: AsyncSession, storage: Any, user: Any, project_id: UUID, rows: list[list[Any]]
) -> tuple[Document, Any]:
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    document = await UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=revisions,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="schedule.xlsx", file=BytesIO(_xlsx(rows))),
        document_type=DocumentType.SCHEDULE,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    [revision] = await revisions.list_lineage(document.id, user.tenant_id)
    return document, revision


async def _reupload(db: AsyncSession, storage: Any, user: Any, document: Document,
                    rows: list[list[Any]]) -> Any:
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    await ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        revision_repository=revisions,
        storage_service=storage,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        tenant_id=user.tenant_id,
        document_id=document.id,
        file_content=_xlsx(rows),
        user_id=user.id,
    )
    return (await revisions.list_lineage(document.id, user.tenant_id))[-1]


async def _human_wbs(
    db: AsyncSession, tenant_id: UUID, project_id: UUID, *, root_code: str = "1",
    root_source_document_id: UUID | None = None,
) -> dict[str, UUID]:
    """A human canonical WBS: root + human child, manually verified RACI, linked BOM.

    ``root_source_document_id`` reproduces a root a pre-#852 schedule parse produced
    (legacy data that already exists): the child beneath it is human work.
    """
    root, child = await seed_legacy_from_dicts(
        db, project_id,
        [
            {"code": root_code, "name": "Civil works (human)"},
            {"code": f"{root_code}.1", "name": "Foundations (human child)",
             "parent_code": root_code},
        ],
        tenant_id,
    )
    if root_source_document_id is not None:
        await db.execute(
            text("UPDATE wbs_nodes SET source_document_id = :d WHERE id = :id"),
            {"d": root_source_document_id, "id": root.id},
        )
    await db.commit()
    stakeholder = StakeholderORM(id=uuid4(), tenant_id=tenant_id, project_id=project_id, name="PM")
    db.add(stakeholder)
    await db.flush()
    rows = [
        StakeholderWBSRaciORM(
            tenant_id=tenant_id, project_id=project_id, stakeholder_id=stakeholder.id,
            wbs_item_id=node_id, raci_role=RACIRole.ACCOUNTABLE,
            generated_automatically=False, manually_verified=True,
        )
        for node_id in (root.id, child.id)
    ]
    bom = BOMItemORM(id=uuid4(), project_id=project_id, item_name="Rebar",
                     quantity=Decimal("4"), wbs_item_id=child.id)
    db.add_all([*rows, bom])
    await db.commit()
    return {"root": root.id, "child": child.id, "bom": bom.id}


async def _canonical(db: AsyncSession, *project_ids: UUID) -> dict[str, list[tuple[Any, ...]]]:
    """Every canonical WBS fact a schedule write could touch, row by row."""
    await db.commit()
    params = {"p": list(project_ids)}
    wbs = await db.execute(
        text("SELECT id, project_id, tenant_id, code, name, parent_id, source_document_id, lft, "
             "rgt, depth, planned_start, planned_end, version, metadata, updated_at "
             "FROM wbs_nodes WHERE project_id = ANY(:p) ORDER BY project_id, code"),
        params,
    )
    raci = await db.execute(
        text("SELECT id, wbs_item_id, raci_role::text, manually_verified, generated_automatically "
             "FROM stakeholder_wbs_raci WHERE project_id = ANY(:p) ORDER BY id"),
        params,
    )
    bom = await db.execute(
        text("SELECT id, wbs_item_id FROM procurement_bom_items WHERE project_id = ANY(:p) "
             "ORDER BY id"),
        params,
    )
    return {
        "wbs": [tuple(r) for r in wbs.all()],
        "raci": [tuple(r) for r in raci.all()],
        "bom": [tuple(r) for r in bom.all()],
    }


async def _document_state(db: AsyncSession, document_id: UUID) -> dict[str, Any]:
    await db.commit()
    row = (
        await db.execute(
            text("SELECT upload_status::text AS status, parsing_error, document_metadata "
                 "FROM documents WHERE id = :d"),
            {"d": document_id},
        )
    ).one()
    chunks = (
        await db.execute(
            text("SELECT content, metadata->>'revision_id' AS revision_id "
                 "FROM document_chunks WHERE document_id = :d"),
            {"d": document_id},
        )
    ).all()
    return {
        "status": row.status,
        "parsing_error": row.parsing_error,
        "metadata": dict(row.document_metadata or {}),
        "chunks": [(c.content, UUID(c.revision_id) if c.revision_id else None) for c in chunks],
    }


async def _reparse_from_source(storage: Any, document: Document, revision: Any) -> list[str]:
    """Recover the structured schedule from the immutable, hash-verified revision."""
    path = await fetch_source_file(storage=storage, document=document, revision=revision)
    return [row["task"] for row in await ExcelFileParser().parse_schedule(path)]


# ── 1, 8, 9, 10: a project with NO canonical WBS ─────────────────────────────


async def test_schedule_upload_creates_no_first_wbs_and_stays_reparsable(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    document, revision = await _upload_schedule(db, worker, test_user, project_id, SCHEDULE_V1)

    result = await ingestion_tasks._process(document.id, revision.revision_id)

    assert result["status"] == "success", result
    # 1: no canonical WBS appears -- a schedule is not Baseline #1.
    assert await _canonical(db, project_id) == {"wbs": [], "raci": [], "bom": []}
    # The extraction summary reports what was observed, and that no WBS was written.
    summary = result["details"]["extraction_summary"]
    assert summary["wbs_items"] == 0
    assert summary["schedule_activities"] == 3
    # 10: the document reaches PARSED (pending analysis), with no parsing error.
    state = await _document_state(db, document.id)
    assert state["status"] == "parsed_pending_analysis"
    assert state["parsing_error"] is None
    # 8: the schedule rows are retrievable via RAG, bound to the parsed revision.
    rag_text = "\n".join(content for content, _ in state["chunks"])
    for task in ("Mobilisation", "Excavation", "Topping out"):
        assert task in rag_text
    assert "WBS: 2.1" in rag_text and "Predecessors: 2" in rag_text
    assert {rev for _, rev in state["chunks"]} == {revision.revision_id}
    # 9: the immutable source revision is re-fetchable and deterministically reparsable.
    assert await _reparse_from_source(worker, document, revision) == [
        "Mobilisation", "Excavation", "Topping out",
    ]
    # Known consequence (documented): until Schedule Temporal Intelligence exists, a
    # schedule upload no longer feeds structured TIME clauses via canonical WBS dates.
    assert await build_schedule_clauses(db, project_id, tenant_id) == []


# ── 2, 3, 6, 7, 11: an existing human WBS, other projects and tenants ────────


async def test_schedule_never_augments_or_replaces_an_existing_wbs(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    sibling_project = await _project(db, tenant_id)
    other_tenant_project = await _project(db, uuid4())
    await _human_wbs(db, tenant_id, project_id)
    await _human_wbs(db, tenant_id, sibling_project)
    other_tenant_id = (
        await db.execute(text("SELECT tenant_id FROM projects WHERE id = :p"),
                         {"p": other_tenant_project})
    ).scalar_one()
    await _human_wbs(db, other_tenant_id, other_tenant_project)
    before = await _canonical(db, project_id, sibling_project, other_tenant_project)

    document, revision = await _upload_schedule(db, worker, test_user, project_id, SCHEDULE_V1)
    result = await ingestion_tasks._process(document.id, revision.revision_id)

    assert result["status"] == "success", result
    # 3 / 6 / 7 / 11: nothing added, nothing renumbered, RACI and BOM links intact,
    # in this project, a sibling project and another tenant.
    assert await _canonical(db, project_id, sibling_project, other_tenant_project) == before
    assert (await _document_state(db, document.id))["status"] == "parsed_pending_analysis"


async def test_schedule_codes_matching_human_codes_are_not_identity(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """2: visible schedule codes equal to human codes neither rename nor relink nodes."""
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    await _human_wbs(db, tenant_id, project_id)
    before = await _canonical(db, project_id)
    same_codes = [
        ["1", "Civil works (schedule says otherwise)", datetime(2026, 1, 5),
         datetime(2026, 1, 9), 5, None],
        ["1.1", "Piling (schedule)", datetime(2026, 1, 12), datetime(2026, 1, 16), 5, "1"],
    ]

    document, revision = await _upload_schedule(db, worker, test_user, project_id, same_codes)
    result = await ingestion_tasks._process(document.id, revision.revision_id)

    assert result["status"] == "success", result
    after = await _canonical(db, project_id)
    assert after == before
    assert [row[4] for row in after["wbs"]] == ["Civil works (human)", "Foundations (human child)"]
    assert all(row[10] is None and row[11] is None for row in after["wbs"]), (
        "schedule dates must not be grafted onto human nodes by code"
    )


# ── 4, 5, 6, 7: reparse over legacy schedule-produced nodes ──────────────────


async def test_reparse_is_stable_and_never_deletes_human_children(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """A root a pre-#852 parse of THIS schedule produced, with human work beneath it.

    The old ``replace_for_source_document`` deleted that root WITH ITS SUBTREE on
    every reparse: the human child, its manually verified RACI (cascade) and its
    BOM link (set NULL) went with it.
    """
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    document, revision_1 = await _upload_schedule(db, worker, test_user, project_id, SCHEDULE_V1)
    ids = await _human_wbs(
        db, tenant_id, project_id, root_code="S1", root_source_document_id=document.id
    )
    before = await _canonical(db, project_id)
    assert len(before["wbs"]) == 2 and len(before["raci"]) == 2

    first = await ingestion_tasks._process(document.id, revision_1.revision_id)
    assert first["status"] == "success", first
    assert await _canonical(db, project_id) == before

    # 4: reparse of a new revision (V2), then again (V3 = V1 bytes): stable.
    for rows in (SCHEDULE_V2, SCHEDULE_V1):
        revision = await _reupload(db, worker, test_user, document, rows)
        result = await ingestion_tasks._process(document.id, revision.revision_id)
        assert result["status"] == "success", result
        after = await _canonical(db, project_id)
        assert after == before
        state = await _document_state(db, document.id)
        assert state["status"] == "parsed_pending_analysis"
        assert any(rev == revision.revision_id for _, rev in state["chunks"])

    # 5 / 6 / 7: the human child, its verified RACI and its BOM link all survive.
    final = await _canonical(db, project_id)
    assert ids["child"] in {row[0] for row in final["wbs"]}
    assert {row[1] for row in final["raci"]} == {ids["root"], ids["child"]}
    assert all(row[3] is True for row in final["raci"])
    assert final["bom"] == [(ids["bom"], ids["child"])]


# ── the documents parse endpoint wiring (second caller) ──────────────────────


async def test_parse_endpoint_wiring_writes_no_wbs_and_keeps_parsed_text(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    await _human_wbs(db, tenant_id, project_id)
    before = await _canonical(db, project_id)
    document, _revision = await _upload_schedule(db, worker, test_user, project_id, SCHEDULE_V1)

    doc_repo = SqlAlchemyDocumentRepository(db)
    use_case = ParseDocumentUseCase(
        document_repository=doc_repo,
        storage_service=worker,
        file_parser_service=ingestion_tasks.file_parser,
        entity_extraction_service=get_entity_extraction_service(
            user_id=test_user.id, db=db, doc_repo=doc_repo
        ),
        rag_ingestion_service=SqlAlchemyRagIngestionService(db_session=db),
        revision_repository=SqlAlchemyDocumentRevisionRepository(db),
    )
    await use_case.execute(tenant_id=tenant_id, document_id=document.id, user_id=test_user.id)

    assert await _canonical(db, project_id) == before
    state = await _document_state(db, document.id)
    # 8: parsed_text carries the schedule rows (parse endpoint Priority 3).
    assert "Excavation | start: 2026-01-19" in state["metadata"]["parsed_text"]
    assert state["parsing_error"] is None
