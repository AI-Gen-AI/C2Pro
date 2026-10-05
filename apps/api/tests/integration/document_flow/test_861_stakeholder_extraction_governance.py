"""#861 -- contract ingestion records stakeholder OBSERVATIONS, never approvals.

TS-INT-861-STAKEHOLDER-GOVERNANCE-001. REAL PostgreSQL, a REAL ``.docx`` contract
uploaded and reuploaded through the real use cases, the REAL ingestion worker
``_process`` (real composite / DOCX parser, real entity extraction, real #711
processing authority and staged stakeholder repository), the REAL documents parse
endpoint wiring (``get_entity_extraction_service``), and the REAL human review use
case. Only object storage (local), embeddings and the broker are replaced.

* an email found in a contract becomes a ``PENDING`` stakeholder with no reviewer
  provenance (the uploader is not recorded as having reviewed it), carrying
  ``stakeholder_metadata.source_document_id``;
* a reparse / re-upload never duplicates a stakeholder (same normalized email in
  the same project + tenant) and never downgrades or overwrites a stakeholder a
  human approved, rejected or corrected;
* other projects and tenants are untouched; the human create API is unchanged.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import docx
import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.approval import ApprovalStatus
from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
from src.core.tasks import ingestion_tasks
from src.documents.adapters.http.router import get_entity_extraction_service
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag import rag_service as rag_service_module
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Document, DocumentType
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase
from src.stakeholders.application.dtos import StakeholderCreateRequest
from src.stakeholders.application.review_stakeholder_approval_use_case import (
    ReviewStakeholderApprovalUseCase,
)
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application import project_snapshot_trigger

pytestmark = pytest.mark.asyncio

CONTRACT_V1 = [
    "CONSTRUCTION CONTRACT",
    "Employer representative: jane.doe@owner-example.com",
    "Contractor site manager: Bob.Builder@contractor-example.com",
    "Notices may also be sent to JANE.DOE@owner-example.com.",
]
CONTRACT_V2 = CONTRACT_V1 + ["New design manager: carol@designer-example.com"]


def _docx(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ── harness: the real worker on its own connections (as in #852 / #860) ──────


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


async def _tenant(db: AsyncSession, tenant_id: UUID) -> None:
    if await db.get(Tenant, tenant_id) is None:
        db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                      subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0))
        await db.commit()


async def _project(db: AsyncSession, tenant_id: UUID) -> UUID:
    await _tenant(db, tenant_id)
    project_id = uuid4()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
             "created_at, updated_at) VALUES (:id, :tid, 'p861', :code, 'construction', "
             "'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return project_id


async def _reviewer(db: AsyncSession, tenant_id: UUID) -> UUID:
    """A human reviewer distinct from the document uploader."""
    user = User(id=uuid4(), tenant_id=tenant_id, email=f"rev-{uuid4().hex[:8]}@example.com",
                hashed_password="x", first_name="Rita", last_name="Reviewer",
                role=UserRole.ADMIN, is_active=True, is_verified=True)
    db.add(user)
    await db.commit()
    return user.id


async def _upload_contract(db: AsyncSession, storage: Any, user: Any, project_id: UUID,
                           paragraphs: list[str]) -> tuple[Document, Any]:
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    document = await UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=revisions,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="contract.docx", file=BytesIO(_docx(paragraphs))),
        document_type=DocumentType.CONTRACT,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    [revision] = await revisions.list_lineage(document.id, user.tenant_id)
    return document, revision


async def _reupload(db: AsyncSession, storage: Any, user: Any, document: Document,
                    paragraphs: list[str]) -> Any:
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    await ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        revision_repository=revisions,
        storage_service=storage,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        tenant_id=user.tenant_id,
        document_id=document.id,
        file_content=_docx(paragraphs),
        user_id=user.id,
    )
    return (await revisions.list_lineage(document.id, user.tenant_id))[-1]


async def _stakeholders(db: AsyncSession, *project_ids: UUID) -> list[dict[str, Any]]:
    await db.commit()
    rows = await db.execute(
        text("SELECT id, project_id, tenant_id, name, lower(email) AS email, "
             "approval_status::text AS status, reviewed_by, reviewed_at, review_comment, "
             "extracted_from_document_id, stakeholder_metadata, updated_at "
             "FROM stakeholders WHERE project_id = ANY(:p) ORDER BY project_id, email, id"),
        {"p": list(project_ids)},
    )
    return [dict(row._mapping) for row in rows.all()]


async def _human_create(db: AsyncSession, user: Any, project_id: UUID, email: str,
                        tenant_id: UUID | None = None) -> UUID:
    created = await CreateStakeholderUseCase(
        repository=SqlAlchemyStakeholderRepository(db),
        document_repository=SqlAlchemyDocumentRepository(db),
    ).execute(project_id=project_id, user_id=user.id,
              payload=StakeholderCreateRequest(name="Human Entered", email=email),
              tenant_id=tenant_id or user.tenant_id)
    return created.id


async def _review(db: AsyncSession, tenant_id: UUID, stakeholder_id: UUID, reviewer: UUID,
                  status: ApprovalStatus, corrections: dict[str, Any] | None = None) -> None:
    await ReviewStakeholderApprovalUseCase(SqlAlchemyStakeholderRepository(db)).execute(
        tenant_id=tenant_id, stakeholder_id=stakeholder_id, status=status,
        correction_data=corrections, feedback_comment=f"human {status.value}",
        user_id=reviewer,
    )


# ── 1-5, 15: first upload ────────────────────────────────────────────────────


async def test_contract_upload_records_pending_observations_without_reviewer(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    document, revision = await _upload_contract(db, worker, test_user, project_id, CONTRACT_V1)

    result = await ingestion_tasks._process(document.id, revision.revision_id)

    assert result["status"] == "success", result
    rows = await _stakeholders(db, project_id)
    # Two people: the two casings of Jane's address are one stakeholder.
    assert [r["email"] for r in rows] == ["bob.builder@contractor-example.com",
                                          "jane.doe@owner-example.com"]
    for row in rows:
        assert row["status"] == ApprovalStatus.PENDING.value
        assert row["reviewed_by"] is None  # the uploader did NOT review it
        assert row["reviewed_at"] is None
        assert row["review_comment"] is None
        assert row["stakeholder_metadata"]["source_document_id"] == str(document.id)
        assert row["stakeholder_metadata"]["origin"] == "automated_extraction"
        assert row["extracted_from_document_id"] is None
    assert result["details"]["extraction_summary"]["stakeholders"] == 2


# ── 8-12: human review survives every reparse ────────────────────────────────


async def test_reparse_never_duplicates_and_never_overwrites_human_decisions(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    reviewer = await _reviewer(db, tenant_id)
    document, revision = await _upload_contract(db, worker, test_user, project_id, CONTRACT_V1)
    assert (await ingestion_tasks._process(document.id, revision.revision_id))["status"] == \
        "success"
    jane, bob = sorted(await _stakeholders(db, project_id), key=lambda r: r["email"],
                       reverse=True)

    await _review(db, tenant_id, jane["id"], reviewer, ApprovalStatus.APPROVED)
    await _review(db, tenant_id, bob["id"], reviewer, ApprovalStatus.REJECTED)
    reviewed = {r["id"]: r for r in await _stakeholders(db, project_id)}
    assert reviewed[jane["id"]]["reviewed_by"] == reviewer  # 8: the actual reviewer
    assert reviewed[jane["id"]]["status"] == ApprovalStatus.APPROVED.value
    assert reviewed[bob["id"]]["reviewed_by"] == reviewer  # 9
    assert reviewed[bob["id"]]["status"] == ApprovalStatus.REJECTED.value

    # 10-12: reparse the same revision, then re-upload a V2 that adds one person.
    assert (await ingestion_tasks._process(document.id, revision.revision_id))["status"] in {
        "success", "already_ingested"}
    revision_2 = await _reupload(db, worker, test_user, document, CONTRACT_V2)
    assert (await ingestion_tasks._process(document.id, revision_2.revision_id))["status"] == \
        "success"
    service = get_entity_extraction_service(user_id=test_user.id, db=db,
                                            doc_repo=SqlAlchemyDocumentRepository(db))
    await service.extract_entities_from_document(
        document=document,
        parsed_payload={"text_blocks": [{"text": " ".join(CONTRACT_V2)}]},
        tenant_id=tenant_id,
    )

    after = {r["id"]: r for r in await _stakeholders(db, project_id)}
    assert {k: after[k] for k in reviewed} == reviewed  # untouched, byte for byte
    new = [r for k, r in after.items() if k not in reviewed]
    assert [r["email"] for r in new] == ["carol@designer-example.com"]
    assert new[0]["status"] == ApprovalStatus.PENDING.value and new[0]["reviewed_by"] is None


async def test_corrected_stakeholder_is_not_reset_by_rediscovery(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    reviewer = await _reviewer(db, tenant_id)
    document, revision = await _upload_contract(db, worker, test_user, project_id, CONTRACT_V1)
    await ingestion_tasks._process(document.id, revision.revision_id)
    jane = next(r for r in await _stakeholders(db, project_id) if r["email"].startswith("jane"))
    await _review(db, tenant_id, jane["id"], reviewer, ApprovalStatus.APPROVED,
                  corrections={"name": "Jane Doe (Employer's Representative)"})
    corrected = {r["id"]: r for r in await _stakeholders(db, project_id)}
    assert corrected[jane["id"]]["status"] == ApprovalStatus.CORRECTED.value

    service = get_entity_extraction_service(user_id=test_user.id, db=db,
                                            doc_repo=SqlAlchemyDocumentRepository(db))
    await service.extract_entities_from_document(
        document=document, parsed_payload={"text_blocks": [{"text": " ".join(CONTRACT_V1)}]},
        tenant_id=tenant_id,
    )

    assert {r["id"]: r for r in await _stakeholders(db, project_id)} == corrected


# ── 7, 13: manual API unchanged; other projects / tenants untouched ──────────


async def test_human_create_and_other_scopes_are_preserved(
    db: AsyncSession, worker: Any, test_user: Any, test_tenant_2: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    sibling = await _project(db, tenant_id)
    foreign = await _project(db, test_tenant_2.id)
    manual_id = await _human_create(db, test_user, sibling, "jane.doe@owner-example.com")
    await db.execute(
        text("INSERT INTO stakeholders (id, tenant_id, project_id, name, email, power_level, "
             "interest_level, approval_status, stakeholder_metadata, created_at, updated_at) "
             "VALUES (:id, :t, :p, 'Foreign Jane', 'jane.doe@owner-example.com', 'medium', "
             "'medium', 'REJECTED', '{}', now(), now())"),
        {"id": uuid4(), "t": test_tenant_2.id, "p": foreign},
    )
    await db.commit()
    untouched = await _stakeholders(db, sibling, foreign)
    [manual] = [r for r in untouched if r["id"] == manual_id]
    # 7: the explicit human create keeps its semantics.
    assert manual["status"] == ApprovalStatus.APPROVED.value
    assert manual["reviewed_by"] == test_user.id and manual["reviewed_at"] is not None

    document, revision = await _upload_contract(db, worker, test_user, project_id, CONTRACT_V1)
    assert (await ingestion_tasks._process(document.id, revision.revision_id))["status"] == \
        "success"

    # 13: the same email elsewhere neither blocks this project nor is touched.
    assert [r["status"] for r in await _stakeholders(db, project_id)] == [
        ApprovalStatus.PENDING.value, ApprovalStatus.PENDING.value]
    assert await _stakeholders(db, sibling, foreign) == untouched
