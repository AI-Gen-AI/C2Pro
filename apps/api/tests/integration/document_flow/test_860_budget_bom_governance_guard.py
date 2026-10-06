"""#860 -- BUDGET ingestion must not delete or replace canonical / manual BOM.

TS-INT-860-BUDGET-BOM-GOVERNANCE-001. REAL PostgreSQL, a REAL ``.xlsx`` budget
uploaded through the real upload / reupload use cases, the REAL ingestion worker
``_process`` (real composite / Excel parser, real entity extraction, real #711
processing authority), the REAL documents parse endpoint wiring
(``get_entity_extraction_service`` + ``ParseDocumentUseCase``) and the REAL
coherence budget clause builder. Only object storage (local), embeddings and the
broker are replaced.

A budget LINE is not a canonical BOM ITEM, and ``procurement_bom_items`` is a
mixed legacy object (manual procurement BOM, historical budget-derived rows,
procurement edits). Until a revision-bound Budget / Cost model exists:

* budget ingestion only observes a budget: no BOM row is created, deleted,
  replaced, reset or relinked -- not manual rows (``source_document_id IS NULL``,
  which the old "orphan sweep" deleted), not procurement-edited legacy rows, not
  other projects' or tenants' rows;
* the budget stays recoverable: the immutable revision is re-fetchable and
  deterministically reparsable; ``stated_total`` / ``parsed_text`` behave as they
  already did; the document reaches ``PARSED_PENDING_ANALYSIS``;
* coherence never reads the BOM table as budget truth: no ``bom-*`` line
  clauses, no ``budget_items`` built from BOM, so DET-BUD-LINEITEM / SUM /
  INTERNAL are not evaluated from it (never pass-by-absence), while the budget
  document's own declared total still reaches the rules that only need it.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
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

from src.coherence.budget_clause_builder import build_budget_clauses
from src.coherence.cross_document import assemble_cross_doc_inputs
from src.coherence.rules_engine.base import ApplicabilityState
from src.coherence.rules_engine.deterministic import (
    BudgetInternalConsistencyEvaluator,
    BudgetLineItemEvaluator,
    BudgetSumMismatchEvaluator,
)
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
from src.procurement.domain.models import ProcurementStatus
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application import project_snapshot_trigger
from tests.support.legacy_wbs import seed_legacy_from_dicts

pytestmark = pytest.mark.asyncio

HEADERS = ["Item", "Quantity", "Unit", "Unit Price", "Total"]
BUDGET_V1 = [
    ["Concrete C30", 10, "m3", 100, 1000],
    ["Steel rebar", 2, "t", 900, 1800],
    ["Total presupuesto", None, None, None, 2800],
]
BUDGET_V2 = [
    ["Concrete C30", 12, "m3", 100, 1200],
    ["Steel rebar", 2, "t", 950, 1900],
    ["Formwork", 30, "m2", 20, 600],
    ["Total presupuesto", None, None, None, 3700],
]
LINE_RULES = (BudgetLineItemEvaluator(), BudgetSumMismatchEvaluator(),
              BudgetInternalConsistencyEvaluator())


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
             "created_at, updated_at) VALUES (:id, :tid, 'p860', :code, 'construction', "
             "'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return project_id


async def _upload_budget(
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
        file=UploadFile(filename="budget.xlsx", file=BytesIO(_xlsx(rows))),
        document_type=DocumentType.BUDGET,
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


async def _manual_bom(db: AsyncSession, project_id: UUID, name: str = "Manually added steel"
                      ) -> UUID:
    """A human-created BOM item: ``POST /procurement/bom`` leaves no source document."""
    row = BOMItemORM(id=uuid4(), project_id=project_id, item_name=name,
                     quantity=Decimal("5"), unit="t", unit_price=Decimal("900"),
                     total_price=Decimal("4500"), supplier="ACME Steel")
    db.add(row)
    await db.commit()
    return row.id


async def _procurement_edited_legacy_row(
    db: AsyncSession, tenant_id: UUID, project_id: UUID, budget_document_id: UUID
) -> UUID:
    """A row an earlier (pre-#860) budget parse produced, since edited by procurement."""
    [node] = await seed_legacy_from_dicts(
        db, project_id, [{"code": "1", "name": "Structure (human WBS)"}], tenant_id
    )
    await db.commit()
    row = BOMItemORM(
        id=uuid4(), project_id=project_id, item_name="Concrete C30", quantity=Decimal("10"),
        unit="m3", unit_price=Decimal("100"), total_price=Decimal("1000"),
        source_document_id=budget_document_id, supplier="Hormigones SA",
        procurement_status=ProcurementStatus.ORDERED, lead_time_days=21,
        production_time_days=7, transit_time_days=3, incoterm="DAP",
        wbs_item_id=node.id, contract_clause_id=uuid4(),
        bom_metadata={"source_document_id": str(budget_document_id), "po": "PO-0042"},
    )
    db.add(row)
    await db.commit()
    return row.id


async def _bom(db: AsyncSession, *project_ids: UUID) -> list[tuple[Any, ...]]:
    """Every BOM fact a budget write could touch, row by row.

    The table has no timestamps; ``id`` + every column catches a delete-and-recreate
    (new ids), a reset (status / supplier / timing / incoterm) or an unlink.
    """
    await db.commit()
    rows = await db.execute(
        text("SELECT id, project_id, item_name, quantity, unit, unit_price, total_price, "
             "currency, supplier, procurement_status::text, lead_time_days, "
             "production_time_days, transit_time_days, incoterm, wbs_item_id, "
             "contract_clause_id, source_document_id, budget_item_id, bom_metadata "
             "FROM procurement_bom_items "
             "WHERE project_id = ANY(:p) ORDER BY project_id, item_name, id"),
        {"p": list(project_ids)},
    )
    return [tuple(r) for r in rows.all()]


async def _document_state(db: AsyncSession, document_id: UUID) -> dict[str, Any]:
    await db.commit()
    row = (
        await db.execute(
            text("SELECT upload_status::text AS status, parsing_error, document_metadata "
                 "FROM documents WHERE id = :d"),
            {"d": document_id},
        )
    ).one()
    return {"status": row.status, "parsing_error": row.parsing_error,
            "metadata": dict(row.document_metadata or {})}


async def _reparse_from_source(storage: Any, document: Document, revision: Any
                               ) -> tuple[list[str], float | None]:
    """Recover the structured budget from the immutable, hash-verified revision."""
    path = await fetch_source_file(storage=storage, document=document, revision=revision)
    rows = await ExcelFileParser().parse_budget(path)
    return [row["item"] for row in rows], getattr(rows, "stated_total", None)


# ── 3, 16, 17, 18, 21: a project with NO BOM ────────────────────────────────


async def test_budget_upload_creates_no_bom_and_stays_reparsable(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    document, revision = await _upload_budget(db, worker, test_user, project_id, BUDGET_V1)

    result = await ingestion_tasks._process(document.id, revision.revision_id)

    assert result["status"] == "success", result
    # 3: no canonical BOM is created from budget lines.
    assert await _bom(db, project_id) == []
    summary = result["details"]["extraction_summary"]
    assert summary["bom_items"] == 0
    assert summary["budget_lines"] == 2
    # 21: the document reaches PARSED (pending analysis) without a parsing error.
    state = await _document_state(db, document.id)
    assert state["status"] == "parsed_pending_analysis"
    assert state["parsing_error"] is None
    # 17 / 18: the immutable revision is re-fetchable and deterministically reparsable.
    assert await _reparse_from_source(worker, document, revision) == (
        ["Concrete C30", "Steel rebar"], 2800.0,
    )


# ── 1, 2, 4, 5, 6, 8: manual + procurement-edited BOM, repeated revisions ────


async def test_manual_and_procurement_edited_bom_survive_every_budget_reparse(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    sibling_project = await _project(db, tenant_id)
    other_tenant_project = await _project(db, uuid4())
    document, revision_1 = await _upload_budget(db, worker, test_user, project_id, BUDGET_V1)
    manual_id = await _manual_bom(db, project_id)
    legacy_id = await _procurement_edited_legacy_row(db, tenant_id, project_id, document.id)
    await _manual_bom(db, sibling_project, "Sibling manual BOM")
    await _manual_bom(db, other_tenant_project, "Other tenant manual BOM")
    scope = (project_id, sibling_project, other_tenant_project)
    before = await _bom(db, *scope)
    assert len(before) == 4

    # 5: parse; 6: new revisions (V2, then V1 bytes again) -- each one reparsed.
    first = await ingestion_tasks._process(document.id, revision_1.revision_id)
    assert first["status"] == "success", first
    assert await _bom(db, *scope) == before
    for rows in (BUDGET_V2, BUDGET_V1):
        revision = await _reupload(db, worker, test_user, document, rows)
        result = await ingestion_tasks._process(document.id, revision.revision_id)
        assert result["status"] == "success", result
        assert await _bom(db, *scope) == before
        assert (await _document_state(db, document.id))["status"] == "parsed_pending_analysis"

    # 1: the manual row survives; 2: the procurement edits survive untouched.
    rows = {row[0]: row for row in await _bom(db, project_id)}
    assert set(rows) == {manual_id, legacy_id}
    legacy = rows[legacy_id]
    assert legacy[8:16] == before[[r[0] for r in before].index(legacy_id)][8:16]
    assert legacy[8] == "Hormigones SA" and legacy[9] == "ordered"
    assert legacy[13] == "DAP" and legacy[14] is not None and legacy[15] is not None


# ── the documents parse endpoint wiring (second caller) ──────────────────────


async def test_parse_endpoint_writes_no_bom_and_keeps_stated_total(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    manual_id = await _manual_bom(db, project_id)
    before = await _bom(db, project_id)
    document, _revision = await _upload_budget(db, worker, test_user, project_id, BUDGET_V1)

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

    # 4 / 1: the canonical BOM (here the manual row) is byte-identical.
    assert await _bom(db, project_id) == before
    assert [row[0] for row in before] == [manual_id]
    state = await _document_state(db, document.id)
    # 20: stated_total behaves as already defined (parse endpoint persists it).
    assert state["metadata"]["stated_total"] == 2800.0
    # 19: parsed_text behaves as already defined -- a flat .xlsx budget has none.
    assert "parsed_text" not in state["metadata"]
    assert state["parsing_error"] is None


# ── 9-14: coherence never reads the BOM table as budget truth ────────────────


async def test_coherence_never_treats_bom_rows_as_budget_truth(
    db: AsyncSession, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    budget_doc = uuid4()
    await db.execute(
        text("INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
             "upload_status, version, storage_encrypted, document_metadata, created_at, "
             "updated_at) VALUES (:id, :tid, :pid, 'budget', 'budget.xlsx', "
             "'parsed_pending_analysis', 1, true, CAST(:meta AS jsonb), now(), now())"),
        {"id": budget_doc, "tid": tenant_id, "pid": project_id,
         "meta": '{"stated_total": 2800.0}'},
    )
    await db.commit()
    await _manual_bom(db, project_id)  # 9: manual procurement BOM
    await _procurement_edited_legacy_row(db, tenant_id, project_id, budget_doc)  # 10: legacy

    clauses = await build_budget_clauses(db, project_id, tenant_id)

    # No BOM row became a budget line, and no line set was assembled from BOM.
    assert not [c for c in clauses if c.id.startswith("bom-")]
    assert all(c.data.get("source") != "procurement_bom" for c in clauses)
    assert all("budget_items" not in c.data for c in clauses)
    # 11-13: the line rules cannot evaluate -- not evaluated, never pass-by-absence.
    for clause in clauses:
        for rule in LINE_RULES:
            assert rule.applicability(clause) is ApplicabilityState.SKIPPED_MISSING_INPUTS
            assert rule.evaluate_v3(clause) is None
    # The unavailability is explicit on the evidence, with an honest reason.
    [declared] = clauses
    assert declared.data["budget_line_items"] == "unavailable"
    assert declared.data["budget_line_items_reason"] == "structured_budget_source_unavailable"
    # 14: rules that only need the budget document's declared total still get it.
    assert declared.data["stated_total"] == 2800.0
    assert assemble_cross_doc_inputs(clauses).budget_total == 2800.0
    assert assemble_cross_doc_inputs(clauses).budget_leaf_sum is None
