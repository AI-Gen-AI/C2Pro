"""P0c temporal intelligence on top of the P0b immutable revision contract.

Refers to Suite ID: TS-INT-P0C-TEMPORAL-001.

Against PostgreSQL, the real repositories and the filesystem store: upload revision A,
re-upload revision B, append the worker's revision-bound analysis events, then prove the
change projection is append-only, evidence/provenance-linked to both immutable revisions,
tenant-scoped on every read, and honest about failures.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant, User
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.document_source import fetch_source_file
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Clause, ClauseType, DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_projection import build_revision_processing_failed_event
from src.temporal.application.revision_change_orchestrator import build_revision_analysis_events
from src.temporal.domain.document_revision import DocumentRevision

pytestmark = pytest.mark.asyncio


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("upload_document_use_case", "reupload_document_use_case"):
        monkeypatch.setattr(
            f"src.documents.application.{module}.enqueue_project_snapshot", lambda **_kwargs: None
        )
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case._enqueue_document_processing",
        lambda _document_id, _revision_id=None: None,
    )


async def _tenant_with_project(db: AsyncSession) -> tuple[UUID, UUID, UUID]:
    tenant_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    db.add_all([
        Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
               subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0),
        User(id=user_id, tenant_id=tenant_id, email=f"u-{user_id.hex[:8]}@test.com",
             hashed_password="h", first_name="t", last_name="t", role="admin"),
    ])
    await db.commit()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
             "VALUES (:id, :tid, 'p0c', :code, 'construction', 'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, user_id, project_id


def _penalty_clause(revision: DocumentRevision, clause_text: str) -> Clause:
    return Clause(
        id=uuid4(), project_id=revision.project_id, tenant_id=revision.tenant_id,
        document_id=revision.document_id, clause_code="PEN-1", clause_type=ClauseType.PENALTY,
        title="Delay penalty", full_text=clause_text,
    )


async def _analyse(db: AsyncSession, revision: DocumentRevision, clause_text: str) -> None:
    """What the worker does for a parsed contract revision (ingestion_tasks._process)."""
    events = SqlAlchemyProjectEventRepository(db)
    prior = await events.list_for_project(revision.project_id, revision.tenant_id)
    for event in await build_revision_analysis_events(
        revision=revision, clauses=[_penalty_clause(revision, clause_text)], existing_events=prior
    ):
        await events.append(event)
    await db.commit()


async def test_revision_change_is_append_only_evidence_linked_and_tenant_scoped(db: AsyncSession, tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant_a, user_a, project_a = await _tenant_with_project(db)
    tenant_b, _user_b, _project_b = await _tenant_with_project(db)
    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    events = SqlAlchemyProjectEventRepository(db)

    document = await UploadDocumentUseCase(
        document_repository=doc_repo, storage_service=storage, project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=rev_repo, event_repository=events,
    ).execute(
        project_id=project_a, file=UploadFile(filename="contract.pdf", file=BytesIO(b"%PDF penalty 1% per week")),
        document_type=DocumentType.CONTRACT, user_id=user_a, tenant_id=tenant_a,
    )
    [revision_a] = await rev_repo.list_lineage(document.id, tenant_a)
    await _analyse(db, revision_a, "The contractor pays a delay penalty of 1% per week.")

    await ReuploadDocumentUseCase(
        document_repository=doc_repo, revision_repository=rev_repo, storage_service=storage, event_repository=events,
    ).execute(tenant_id=tenant_a, document_id=document.id, file_content=b"%PDF penalty 2% per week", user_id=user_a)
    revision_a, revision_b = await rev_repo.list_lineage(document.id, tenant_a)
    await _analyse(db, revision_b, "The contractor pays a delay penalty of 2% per week.")

    # The change projection links both immutable revisions and their content hashes.
    change = await events.get_change_for_revision(
        tenant_id=tenant_a, project_id=project_a, document_id=document.id, revision_id=revision_b.revision_id,
    )
    assert change is not None
    assert change.event_type == "revision.changed"
    assert change.payload["change_cause"] == "BUSINESS_STATE_CHANGED"
    provenance = change.payload["provenance"]
    assert provenance["source_revision_id"] == str(revision_a.revision_id)
    assert provenance["target_revision_id"] == str(revision_b.revision_id)
    assert provenance["source_blob_hash"] == revision_a.blob_hash
    assert provenance["target_blob_hash"] == revision_b.blob_hash
    assert change.payload["changeset"]["changes"], "a modified clause is a real L1 change"

    # Append-only: revision A's analysis snapshot still states A's evidence after B.
    page = await events.page_for_project(project_a, tenant_a, after=None, limit=50)
    snapshots = {event.payload["revision_id"]: event for event in page if event.event_type == "revision.analyzed"}
    assert "1% per week" in snapshots[str(revision_a.revision_id)].payload["clauses"][0]["full_text"]
    assert "2% per week" in snapshots[str(revision_b.revision_id)].payload["clauses"][0]["full_text"]
    assert [event.event_type for event in page].count("revision.ingested") == 2
    # Re-running the worker for an analysed revision appends nothing (idempotent history).
    assert await build_revision_analysis_events(
        revision=revision_b, clauses=[_penalty_clause(revision_b, "anything")],
        existing_events=await events.list_for_project(project_a, tenant_a),
    ) == []

    # Both immutable objects remain the evidence for their revisions.
    assert (await fetch_source_file(storage=storage, document=document, revision=revision_a)).read_bytes() == b"%PDF penalty 1% per week"
    assert (await fetch_source_file(storage=storage, document=document, revision=revision_b)).read_bytes() == b"%PDF penalty 2% per week"

    # Tenant isolation on every temporal read.
    assert await events.page_for_project(project_a, tenant_b, after=None, limit=50) == []
    assert await events.list_for_project(project_a, tenant_b) == []
    assert await events.get_change_for_revision(
        tenant_id=tenant_b, project_id=project_a, document_id=document.id, revision_id=revision_b.revision_id,
    ) is None
    assert await rev_repo.get_by_id(revision_b.revision_id, tenant_b) is None


async def test_revision_without_prior_snapshot_needs_review_and_failure_is_never_no_change(db: AsyncSession, tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant_id, user_id, project_id = await _tenant_with_project(db)
    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    events = SqlAlchemyProjectEventRepository(db)

    document = await UploadDocumentUseCase(
        document_repository=doc_repo, storage_service=storage, project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=rev_repo, event_repository=events,
    ).execute(
        project_id=project_id, file=UploadFile(filename="contract.pdf", file=BytesIO(b"%PDF A")),
        document_type=DocumentType.CONTRACT, user_id=user_id, tenant_id=tenant_id,
    )
    # Revision A is never analysed (e.g. its worker run failed); B arrives.
    [revision_a] = await rev_repo.list_lineage(document.id, tenant_id)
    await events.append(build_revision_processing_failed_event(revision=revision_a, failure_code="analysis_processing_failed"))
    await db.commit()
    await ReuploadDocumentUseCase(
        document_repository=doc_repo, revision_repository=rev_repo, storage_service=storage, event_repository=events,
    ).execute(tenant_id=tenant_id, document_id=document.id, file_content=b"%PDF B", user_id=user_id)
    _revision_a, revision_b = await rev_repo.list_lineage(document.id, tenant_id)
    await _analyse(db, revision_b, "Penalty clause text")

    page = await events.page_for_project(project_id, tenant_id, after=None, limit=50)
    failure = next(event for event in page if event.event_type == "revision.analysis_failed")
    assert failure.payload["state"] == "error" and failure.payload["change_cause"] is None
    analysed_b = next(
        event for event in page
        if event.event_type == "revision.analyzed" and event.payload["revision_id"] == str(revision_b.revision_id)
    )
    assert analysed_b.payload["state"] == "needs_review", "no reliable comparison without A's snapshot"
    assert not any(event.event_type == "revision.changed" for event in page)
