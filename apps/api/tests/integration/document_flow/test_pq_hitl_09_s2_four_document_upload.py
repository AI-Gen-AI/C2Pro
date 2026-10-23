"""PQ-HITL-09 S2: four-document upload and content-addressed revision persistence.

Runs the REAL UploadDocumentUseCase with the real document, revision and project
event repositories against the test database (the #852 harness); only the broker
and storage backend are local. It proves, per matrix invariant:

* CONTENT_ADDRESSED_REVISION_HASH: each family's genesis revision stores the
  SHA-256 of its exact bytes, inside its immutable blob key, with one
  revision.ingested event bound to that revision.
* REJECT_DOCX_ON_STRUCTURED_BUDGET / _SCHEDULE: 400, nothing persisted.
* REJECT_UNSUPPORTED_EXTENSIONS_415: 415, nothing persisted.

Scope limits (kept honest): uploads are sequential in one session, so the
matrix's *concurrent* upload is not exercised; no AI extraction runs; this is
integration evidence, not live UAT (matrix live_uat_status stays NOT_VERIFIED).
"""

from __future__ import annotations

import hashlib
import io
from typing import Any
from uuid import UUID, uuid4

import openpyxl
import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from tests.integration.document_flow.test_852_schedule_wbs_governance_guard import (  # noqa: F401 - fixture
    _project,
    _ProjectRepo,
    worker,
)

pytestmark = pytest.mark.asyncio


def _xlsx(header: list[str], row: list[Any]) -> bytes:
    workbook = openpyxl.Workbook()
    workbook.active.append(header)
    workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# One source per document family of the matrix (sample sources from the fixture).
FAMILIES: tuple[tuple[DocumentType, str, bytes], ...] = (
    (DocumentType.CONTRACT, "contract.pdf",
     b"%PDF-1.4 5.2 Defective work shall be rectified within fourteen (14) days."),
    (DocumentType.BUDGET, "budget.xlsx",
     _xlsx(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency"],
           ["03.01 Earthworks excavation", 1250, "m3", 45, 56250, "EUR"])),
    (DocumentType.SCHEDULE, "schedule.xlsx",
     _xlsx(["Activity", "Name", "Duration", "Predecessor"],
           ["ACT-102", "Foundation Concrete Pour", 14, "ACT-101"])),
    (DocumentType.TECHNICAL_SPEC, "technical-spec.pdf",
     b"%PDF-1.4 Section 4.1.2 Concrete compressive strength shall exceed 35 MPa."),
)


def _use_case(db: AsyncSession, storage: Any) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=SqlAlchemyDocumentRevisionRepository(db),
        event_repository=SqlAlchemyProjectEventRepository(db),
    )


async def _upload(db: AsyncSession, storage: Any, user: Any, project_id: UUID,
                  document_type: DocumentType, filename: str, data: bytes) -> Document:
    return await _use_case(db, storage).execute(
        project_id=project_id, file=UploadFile(io.BytesIO(data), filename=filename),
        document_type=document_type, user_id=user.id, tenant_id=user.tenant_id,
    )


async def _document_count(db: AsyncSession, project_id: UUID) -> int:
    return int(await db.scalar(
        text("SELECT count(*) FROM documents WHERE project_id = :p"), {"p": project_id}
    ))


async def test_four_families_persist_content_addressed_genesis_revisions(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    events = SqlAlchemyProjectEventRepository(db)
    hashes: dict[DocumentType, str] = {}

    for document_type, filename, data in FAMILIES:
        document = await _upload(db, worker, test_user, project_id, document_type, filename, data)
        assert document.document_type is document_type
        assert document.project_id == project_id
        assert document.tenant_id == test_user.tenant_id
        assert document.upload_status is DocumentStatus.UPLOADED

        lineage = await revisions.list_lineage(document.id, test_user.tenant_id)
        assert len(lineage) == 1
        genesis = lineage[0]
        expected = hashlib.sha256(data).hexdigest()
        assert (genesis.rev_no, genesis.parent_revision_id) == (1, None)
        assert genesis.blob_hash == expected
        assert expected in genesis.blob_key
        assert (genesis.project_id, genesis.tenant_id) == (project_id, test_user.tenant_id)
        assert await worker.file_exists(genesis.blob_key)
        # A content-addressed key alone does not prove persisted object integrity.
        stored_path = await worker.download_object(genesis.blob_key)
        stored_bytes = stored_path.read_bytes()
        assert stored_bytes == data
        assert hashlib.sha256(stored_bytes).hexdigest() == genesis.blob_hash

        ingested = [
            event for event in await events.list_for_revision(
                tenant_id=test_user.tenant_id, revision_id=genesis.revision_id
            )
            if event.event_type == "revision.ingested"
        ]
        assert len(ingested) == 1
        assert ingested[0].project_id == project_id
        # The material event carries the same content address and identities.
        assert ingested[0].payload["blob_hash"] == expected
        assert ingested[0].payload["document_id"] == str(document.id)
        assert ingested[0].payload["filename"] == filename
        hashes[document_type] = genesis.blob_hash

    assert len(set(hashes.values())) == 4
    assert await _document_count(db, project_id) == 4

    # Content addressing: identical bytes yield the identical hash for a new
    # document, while revision and document identities stay distinct.
    _, filename, data = FAMILIES[0]
    again = await _upload(db, worker, test_user, project_id, DocumentType.CONTRACT, filename, data)
    again_rev = (await revisions.list_lineage(again.id, test_user.tenant_id))[0]
    assert again_rev.blob_hash == hashes[DocumentType.CONTRACT]

    # Another tenant can never read this lineage.
    assert await revisions.list_lineage(again.id, uuid4()) == []


async def test_tampered_persisted_object_digest_is_detected(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """Negative fixture: altered stored bytes must not match the recorded revision."""
    project_id = await _project(db, test_user.tenant_id)
    document_type, filename, original = FAMILIES[0]
    document = await _upload(
        db, worker, test_user, project_id, document_type, filename, original
    )
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    genesis = (await revisions.list_lineage(document.id, test_user.tenant_id))[0]
    stored_path = await worker.download_object(genesis.blob_key)
    assert hashlib.sha256(stored_path.read_bytes()).hexdigest() == genesis.blob_hash

    stored_path.write_bytes(original + b"tampered")
    retrieved = (await worker.download_object(genesis.blob_key)).read_bytes()
    assert retrieved != original
    assert hashlib.sha256(retrieved).hexdigest() != genesis.blob_hash


@pytest.mark.parametrize("family_index", range(len(FAMILIES)))
async def test_each_family_revision_is_tenant_scoped_and_source_bytes_roundtrip(
    db: AsyncSession, worker: Any, test_user: Any, family_index: int
) -> None:
    """Negative tenant lookup + positive immutable source verification for every family."""
    document_type, filename, data = FAMILIES[family_index]
    project_id = await _project(db, test_user.tenant_id)
    document = await _upload(
        db, worker, test_user, project_id, document_type, filename, data
    )
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    [revision] = await revisions.list_lineage(document.id, test_user.tenant_id)
    assert await revisions.list_lineage(document.id, uuid4()) == []
    assert (revision.tenant_id, revision.project_id) == (
        test_user.tenant_id, project_id
    )
    persisted = (await worker.download_object(revision.blob_key)).read_bytes()
    assert persisted == data
    assert hashlib.sha256(persisted).hexdigest() == revision.blob_hash


@pytest.mark.parametrize("document_type", [DocumentType.BUDGET, DocumentType.SCHEDULE])
async def test_docx_on_structured_family_is_rejected_and_nothing_persists(
    db: AsyncSession, worker: Any, test_user: Any, document_type: DocumentType
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    with pytest.raises(HTTPException) as caught:
        await _upload(db, worker, test_user, project_id, document_type,
                      f"{document_type.value}.docx", b"PK\x03\x04 docx bytes")
    assert caught.value.status_code == 400
    assert await _document_count(db, project_id) == 0


@pytest.mark.parametrize("document_type", [family for family, _, _ in FAMILIES])
@pytest.mark.parametrize("extension", [".exe", ".bin"])
async def test_unsupported_extension_is_415_and_nothing_persists(
    db: AsyncSession, worker: Any, test_user: Any, document_type: DocumentType, extension: str
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    with pytest.raises(HTTPException) as caught:
        await _upload(db, worker, test_user, project_id, document_type,
                      f"source{extension}", b"MZ\x90\x00 not a document")
    assert caught.value.status_code == 415
    assert await _document_count(db, project_id) == 0
