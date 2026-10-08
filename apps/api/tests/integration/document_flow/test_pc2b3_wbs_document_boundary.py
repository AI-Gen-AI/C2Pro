"""PC-2b.3 (#922) acceptance A -- a ``wbs`` document is an EXTERNAL WBS SOURCE, never analysed.

It accepts ``.xlsx``/``.csv``/``.json`` (granted to the WBS type ONLY), and it never enters the
ingestion worker, RAG chunking, the N1-N17 graph, the synchronous parse path, reprocess or the
recovery sweeper. It is parsed only by the deterministic WBS importer, which leaves it PARSED --
never analysis-pending. Real upload/reupload use cases and the real worker functions run against
the test database (the 852 harness), with brokers and embeddings stubbed.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tasks import ingestion_tasks
from src.core.tasks.document_recovery import _sweep_async
from src.documents.adapters.http import router as documents_router
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
    SqlAlchemyRagIngestionService,
)
from src.documents.application.parse_document_use_case import ParseDocumentUseCase
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.trigger_document_analysis_use_case import (
    TriggerDocumentAnalysisUseCase,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.domain.upload_policy import UploadFormatError
from src.documents.ports.rag_ingestion_service import RagIngestionOutcome
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.wbs.adapters.persistence.governance_repository import Actor
from src.wbs.domain.governance import ActorKind
from src.wbs.imports.service import WBSImportService
from tests.integration.document_flow.test_852_schedule_wbs_governance_guard import (  # noqa: F401 - fixture
    _project,
    _ProjectRepo,
    worker,
)

pytestmark = pytest.mark.asyncio

CSV = b"code,name,parent_code\n1,Plant,\n1.1,Civil,1\n"
JSON = b'{"format":"wbs-import/v1","nodes":[{"code":"1","name":"Plant","level":1}]}'


def _xlsx() -> bytes:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["code", "name", "level"])
    sheet.append(["1", "Plant", 1])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def _upload(db: AsyncSession, storage: Any, user: Any, project_id: UUID, data: bytes, filename: str,
                  document_type: DocumentType = DocumentType.WBS) -> Document:
    use_case = UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db), storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=SqlAlchemyDocumentRevisionRepository(db),
        event_repository=SqlAlchemyProjectEventRepository(db),
    )
    return await use_case.execute(project_id=project_id, file=UploadFile(io.BytesIO(data), filename=filename),
                                  document_type=document_type, user_id=user.id, tenant_id=user.tenant_id)


async def _status(db: AsyncSession, document_id: UUID) -> str:
    return str(await db.scalar(text("SELECT upload_status::text FROM documents WHERE id = :d"), {"d": document_id}))


async def _side_effects(db: AsyncSession, document_id: UUID) -> tuple[int, int, int, int]:
    row = (await db.execute(text(
        "SELECT (SELECT count(*) FROM document_chunks WHERE document_id = :d), "
        "(SELECT count(*) FROM document_artifacts WHERE document_id = :d), "
        "(SELECT count(*) FROM clauses WHERE document_id = :d), "
        "(SELECT count(*) FROM document_processing_operations WHERE document_id = :d)"), {"d": document_id})).one()
    return tuple(int(v) for v in row)  # type: ignore[return-value]


async def test_1_2_3_4_the_wbs_type_accepts_xlsx_csv_and_json(db: AsyncSession, worker: Any, test_user: Any) -> None:
    assert DocumentType("wbs") is DocumentType.WBS
    project_id = await _project(db, test_user.tenant_id)
    for data, name in ((_xlsx(), "wbs.xlsx"), (CSV, "wbs.csv"), (JSON, "wbs.json")):
        documents_router._validate_upload_extension(name[name.rfind("."):], DocumentType.WBS)
        document = await _upload(db, worker, test_user, project_id, data, name)
        assert document.document_type is DocumentType.WBS
        lineage = await SqlAlchemyDocumentRevisionRepository(db).list_lineage(document.id, test_user.tenant_id)
        assert len(lineage) == 1  # an immutable revision, exactly like any document
    for ext in (".xls", ".xlsm", ".bc3", ".xer", ".xml", ".ifc", ".pdf"):
        with pytest.raises(HTTPException):
            documents_router._validate_upload_extension(ext, DocumentType.WBS)


async def test_5_csv_and_json_are_never_granted_to_other_types(db: AsyncSession, worker: Any, test_user: Any) -> None:
    project_id = await _project(db, test_user.tenant_id)
    for document_type, name in ((DocumentType.CONTRACT, "contract.csv"), (DocumentType.BUDGET, "budget.json"),
                                (DocumentType.SCHEDULE, "schedule.csv")):
        with pytest.raises(HTTPException) as caught:
            documents_router._validate_upload_extension(name[name.rfind("."):], document_type)
        assert caught.value.status_code == 400
        with pytest.raises(HTTPException) as caught:
            await _upload(db, worker, test_user, project_id, CSV, name, document_type)
        assert caught.value.status_code == 415
        await db.rollback()
    contract = await _upload(db, worker, test_user, project_id, b"%PDF-1.4", "contract.pdf", DocumentType.CONTRACT)
    reupload = ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db), revision_repository=SqlAlchemyDocumentRevisionRepository(db),
        storage_service=worker, event_repository=SqlAlchemyProjectEventRepository(db))
    with pytest.raises(UploadFormatError):
        await reupload.execute(tenant_id=test_user.tenant_id, document_id=contract.id, file_content=CSV,
                               filename="contract.csv", user_id=test_user.id)


async def test_6_the_upload_and_reupload_enqueue_nothing(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    enqueued: list[Any] = []
    monkeypatch.setattr(documents_router, "_enqueue_document_processing", lambda *a, **k: enqueued.append(a) or "t")
    monkeypatch.setattr("src.documents.application.reupload_document_use_case._enqueue_document_processing",
                        lambda *a, **k: enqueued.append(a) or "t")
    use_case = UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db), storage_service=worker,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=SqlAlchemyDocumentRevisionRepository(db),
        event_repository=SqlAlchemyProjectEventRepository(db))
    response = await documents_router.upload_document_for_processing(
        project_id=project_id, user_id=test_user.id, tenant_id=test_user.tenant_id, document_type=DocumentType.WBS,
        file=UploadFile(io.BytesIO(CSV), filename="wbs.csv", size=len(CSV)), upload_use_case=use_case)
    assert response.task_id is None and "never ingested or analysed" in (response.status_detail or "")
    reupload = ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db), revision_repository=SqlAlchemyDocumentRevisionRepository(db),
        storage_service=worker, event_repository=SqlAlchemyProjectEventRepository(db))
    await reupload.execute(tenant_id=test_user.tenant_id, document_id=response.id, file_content=CSV + b"1.2,Elec,1\n",
                           filename="wbs.csv", user_id=test_user.id)
    assert enqueued == []
    assert await _status(db, response.id) == DocumentStatus.UPLOADED.value


async def test_6_7_8_the_worker_rag_and_analysis_refuse_a_wbs_source(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    document = await _upload(db, worker, test_user, project_id, CSV, "wbs.csv")
    await db.commit()
    before = await _status(db, document.id)
    assert await ingestion_tasks._process(document.id) == {
        "status": "not_ingestible", "document_id": str(document.id),
        "reason": ingestion_tasks.WBS_ANALYSIS_EXCLUDED_DETAIL}
    analysed = await ingestion_tasks._run_document_analysis(tenant_id=test_user.tenant_id, document_id=document.id)
    assert analysed["status"] == "not_analysable"
    rag = await SqlAlchemyRagIngestionService(db_session=db, commit=False).ingest_document_chunks(
        document, {"text_blocks": [{"text": "1 Plant 1.1 Civil"}]}, test_user.tenant_id)
    assert rag.outcome is RagIngestionOutcome.NOT_REQUIRED  # 7: zero chunks
    with pytest.raises(ValueError, match="never ingested or analysed"):
        await TriggerDocumentAnalysisUseCase(document_repository=SqlAlchemyDocumentRepository(db)).execute(
            document_id=document.id, tenant_id=test_user.tenant_id)
    with pytest.raises(HTTPException) as caught:
        await ParseDocumentUseCase(document_repository=SqlAlchemyDocumentRepository(db), storage_service=worker,
                                   file_parser_service=Mock(), entity_extraction_service=Mock(),
                                   rag_ingestion_service=Mock()).execute(test_user.tenant_id, document.id, test_user.id)
    assert caught.value.status_code == 409
    await db.rollback()
    assert await _status(db, document.id) == before
    assert await _side_effects(db, document.id) == (0, 0, 0, 0)  # 7/8: no chunk, analysis, clause or operation


async def test_reprocess_is_refused_for_a_wbs_source(db: AsyncSession, worker: Any, test_user: Any) -> None:
    project_id = await _project(db, test_user.tenant_id)
    document = await _upload(db, worker, test_user, project_id, CSV, "wbs.csv")
    await db.execute(text("UPDATE documents SET upload_status = 'error' WHERE id = :d"), {"d": document.id})
    await db.commit()
    with pytest.raises(HTTPException) as caught:
        await documents_router.reprocess_document_endpoint(
            project_id=project_id, document_id=document.id, user_id=test_user.id, tenant_id=test_user.tenant_id,
            repo=SqlAlchemyDocumentRepository(db), pending_review_lookup=lambda *_: {})
    assert caught.value.status_code == 409


@pytest.fixture
async def recovery_index(db: AsyncSession, test_user: Any) -> Any:
    """Restore the #711 documents -> recovery-index trigger the ORM bootstrap drops (see test_worker_loss_recovery).

    The index lives outside ``public`` and keeps rows after the bootstrap's cascade, so this test removes
    its own rows: a stale candidate left behind would be scanned by every later recovery test.
    """
    tenant_id = test_user.tenant_id
    assert (await db.execute(text("SELECT to_regclass('system_recovery.document_work_index')"))).scalar() is not None
    await db.execute(text("DROP TRIGGER IF EXISTS trg_documents_recovery_index ON public.documents"))
    await db.execute(text("CREATE TRIGGER trg_documents_recovery_index AFTER INSERT OR UPDATE ON public.documents "
                          "FOR EACH ROW EXECUTE FUNCTION system_recovery.sync_document_work_index()"))
    await db.commit()
    yield
    await db.rollback()
    # documents are append-only history here (their revision events): park them terminal, then drop
    # this tenant's recovery-index rows so no later recovery test scans them
    await db.execute(text("UPDATE documents SET upload_status = 'error' WHERE tenant_id = :t AND upload_status::text "
                          "IN ('parsed_pending_analysis', 'processing')"), {"t": tenant_id})
    await db.execute(text("DELETE FROM system_recovery.document_work_index WHERE tenant_id = :t"), {"t": tenant_id})
    await db.commit()


async def test_9_a_parsed_wbs_source_is_never_analysis_pending_nor_recovered(
    db: AsyncSession, worker: Any, test_user: Any, recovery_index: Any
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    document = await _upload(db, worker, test_user, project_id, CSV, "wbs.csv")
    await db.commit()
    actor = Actor(user_id=test_user.id, kind=ActorKind.HUMAN, role=str(getattr(test_user.role, "value", test_user.role)))
    result = await WBSImportService(db, storage=worker).create_import(
        project_id=project_id, tenant_id=test_user.tenant_id, actor=actor, document_id=document.id)
    await db.commit()
    assert result.source.status == "READY"
    assert await _status(db, document.id) == DocumentStatus.PARSED.value  # terminal, not parsed_pending_analysis
    # even a WBS row that somehow sat in a recoverable state is never handed back to the pipeline
    stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
    await db.execute(text("UPDATE documents SET upload_status = 'parsed_pending_analysis', updated_at = :t "
                          "WHERE id = :d"), {"d": document.id, "t": stale})
    await db.commit()
    await db.execute(text("UPDATE system_recovery.document_work_index SET updated_at = :t, heartbeat_at = NULL "
                          "WHERE document_id = :d"), {"d": document.id, "t": stale})
    await db.commit()
    indexed = await db.scalar(text("SELECT upload_status FROM system_recovery.document_work_index "
                                   "WHERE document_id = :d"), {"d": document.id})
    assert indexed == DocumentStatus.PARSED_PENDING_ANALYSIS.value  # the sweeper genuinely sees it as a candidate

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def sessions(tenant_id: Any) -> Any:
        if tenant_id is not None:
            await db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)})
        yield db
        await db.commit()

    # control: a contract in exactly the same stale state IS handed back to analysis
    control = await _upload(db, worker, test_user, project_id, b"%PDF-1.4", "contract.pdf", DocumentType.CONTRACT)
    await db.commit()
    await db.execute(text("UPDATE documents SET upload_status = 'parsed_pending_analysis', updated_at = :t "
                          "WHERE id = :d"), {"d": control.id, "t": stale})
    await db.execute(text("UPDATE system_recovery.document_work_index SET updated_at = :t, heartbeat_at = NULL "
                          "WHERE document_id = :d"), {"d": control.id, "t": stale})
    await db.commit()
    ingestion, analysis = Mock(), Mock()
    await _sweep_async(stale_after_seconds=60, session_factory=sessions, ingestion_task=ingestion,
                       analysis_task=analysis)
    dispatched = [call.kwargs.get("kwargs", {}).get("document_id") for call in analysis.apply_async.call_args_list]
    assert str(control.id) in dispatched
    assert str(document.id) not in dispatched
    ingestion.apply_async.assert_not_called()
    assert await _status(db, document.id) == DocumentStatus.PARSED_PENDING_ANALYSIS.value  # untouched, not failed


async def test_9b_the_documents_list_never_offers_analysis_or_retry_for_a_wbs_source(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    from src.documents.application.list_project_documents_use_case import (
        ListProjectDocumentsUseCase,
    )

    class _Projects:
        async def get_by_id(self, _project_id: UUID, _tenant_id: UUID) -> object:
            return object()

    project_id = await _project(db, test_user.tenant_id)
    document = await _upload(db, worker, test_user, project_id, b"code,name,parent_code\n1,A,9\n", "wbs.csv")
    await db.commit()
    actor = Actor(user_id=test_user.id, kind=ActorKind.HUMAN, role=str(getattr(test_user.role, "value", test_user.role)))
    await WBSImportService(db, storage=worker).create_import(
        project_id=project_id, tenant_id=test_user.tenant_id, actor=actor, document_id=document.id)
    await db.commit()  # INVALID import -> the source document is in error (blocking diagnostics)
    listed = await documents_router.list_documents_for_project(
        project_id=project_id, tenant_id=test_user.tenant_id, _user_id=test_user.id, skip=0, limit=20,
        list_use_case=ListProjectDocumentsUseCase(SqlAlchemyDocumentRepository(db), _Projects()),  # type: ignore[arg-type]
        pending_review_lookup=lambda *_: {})
    [item] = [i for i in listed.items if i.id == document.id]
    assert item.retryable is False  # a retry would mean re-analysis: never offered for a WBS source
    assert "blocking diagnostics" in item.status_detail and "analysis" not in item.status_detail.lower()
