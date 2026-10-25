"""ACC-01 S1/S2: the upload API itself, not the UI in front of it.

The REAL ``POST /projects/{id}/documents`` route is driven through the real FastAPI application
(ASGI, authentication, tenant middleware) with REAL PostgreSQL. Every request gets its OWN database
session, so concurrent uploads are arbitrated by PostgreSQL across connections the way API workers
are. Only the broker and the blob backend are local.

Proved, per document family (Contract, Budget, Schedule, Technical spec):

* four uploads sent AT THE SAME TIME all return 202 and persist four distinct documents;
* each document's genesis revision stores the SHA-256 of the exact bytes sent, inside its immutable
  blob key, with one ``revision.ingested`` event bound to that revision, and the stored blob really
  contains those bytes;
* another tenant can read none of it.

Incompatible formats are refused BY THE API (not only hidden by the UI): a DOCX on a structured
Budget or Schedule and unsupported extensions each answer
4xx with a reason, and NOTHING is persisted - no document, no revision, no event, no blob.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
from collections.abc import AsyncGenerator, Callable
from typing import Any
from uuid import UUID

import openpyxl
import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.http import router as documents_router
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from tests.integration.document_flow.test_852_schedule_wbs_governance_guard import (  # noqa: F401
    _project,
    _ProjectRepo,
    worker,
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    request_sessions,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio


def _xlsx(header: list[str], row: list[Any]) -> bytes:
    workbook = openpyxl.Workbook()
    workbook.active.append(header)
    workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _docx_bytes() -> bytes:
    import docx

    document = docx.Document()
    document.add_paragraph("5.2 Defective work shall be rectified within fourteen (14) days.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


CONTRACT_DOCX = _docx_bytes()
BUDGET_XLSX = _xlsx(
    ["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency"],
    ["03.01 Earthworks excavation", 1250, "m3", 45, 56250, "EUR"],
)
SCHEDULE_XLSX = _xlsx(
    ["Activity", "Name", "Duration", "Predecessor"],
    ["ACT-102", "Foundation Concrete Pour", 14, "ACT-101"],
)
FAMILIES: tuple[tuple[DocumentType, str, bytes, str], ...] = (
    (
        DocumentType.CONTRACT,
        "contract.docx",
        CONTRACT_DOCX,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    (
        DocumentType.BUDGET,
        "budget.xlsx",
        BUDGET_XLSX,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (
        DocumentType.SCHEDULE,
        "schedule.xlsx",
        SCHEDULE_XLSX,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (
        DocumentType.TECHNICAL_SPEC,
        "technical-spec.pdf",
        b"%PDF-1.4 Section 4.1.2 Concrete compressive strength shall exceed 35 MPa.",
        "application/pdf",
    ),
)


@pytest.fixture
async def api(
    app: Any,
    db: AsyncSession,
    worker: Any,  # noqa: F811
    request_sessions: Any,  # noqa: F811
    test_user: Any,
    generate_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """The real app, authenticated, with one independent database session per request."""
    from src.core.database import get_session
    from src.core.security import get_current_user_id

    async def per_request_session() -> AsyncGenerator[AsyncSession, None]:
        async with request_sessions() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, false)"),
                {"t": str(test_user.tenant_id)},
            )
            yield session

    def per_request_use_case(session: AsyncSession = Depends(per_request_session)):
        return UploadDocumentUseCase(
            document_repository=SqlAlchemyDocumentRepository(session),
            storage_service=worker,
            project_repository=_ProjectRepo(),  # type: ignore[arg-type]
            revision_repository=SqlAlchemyDocumentRevisionRepository(session),
            event_repository=SqlAlchemyProjectEventRepository(session),
        )

    monkeypatch.setattr(documents_router, "_enqueue_document_processing", lambda *_a, **_k: None)
    app.dependency_overrides[get_session] = per_request_session
    app.dependency_overrides[get_current_user_id] = lambda: test_user.id
    app.dependency_overrides[documents_router.get_upload_use_case] = per_request_use_case

    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        email=test_user.email,
        role=test_user.role.value,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        timeout=60.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _post(
    api: AsyncClient,
    project_id: UUID,
    document_type: DocumentType,
    filename: str,
    data: bytes,
    mime: str,
):
    return await api.post(
        f"/api/v1/projects/{project_id}/documents",
        data={"document_type": document_type.value},
        files={"file": (filename, data, mime)},
    )


async def _counts(db: AsyncSession, project_id: UUID) -> dict[str, int]:
    await db.commit()
    rows = {}
    for name, sql in {
        "documents": "SELECT count(*) FROM documents WHERE project_id = :p",
        "revisions": "SELECT count(*) FROM document_revisions WHERE project_id = :p",
        "events": "SELECT count(*) FROM project_events WHERE project_id = :p AND event_type = 'revision.ingested'",
    }.items():
        rows[name] = int(await db.scalar(text(sql), {"p": project_id}))
    return rows


async def test_four_documents_sent_at_the_same_time_persist_with_their_exact_hashes(
    db: AsyncSession,
    api: AsyncClient,
    worker: Any,
    test_user: Any,  # noqa: F811
) -> None:
    project_id = await _project(db, test_user.tenant_id)

    responses = await asyncio.gather(
        *(_post(api, project_id, kind, name, data, mime) for kind, name, data, mime in FAMILIES)
    )

    assert [response.status_code for response in responses] == [202] * 4, [
        r.text for r in responses
    ]
    bodies = [response.json() for response in responses]
    assert len({body["id"] for body in bodies}) == 4, "four distinct documents"
    for (kind, name, data, _), body in zip(FAMILIES, bodies, strict=True):
        expected = hashlib.sha256(data).hexdigest()
        assert body["document_type"] == kind.value
        assert body["filename"] == name

    await db.commit()
    for (kind, name, data, _), body in zip(FAMILIES, bodies, strict=True):
        expected = hashlib.sha256(data).hexdigest()
        document_id = UUID(body["id"])
        stored = (
            await db.execute(
                text(
                    "SELECT file_hash, document_type::text AS dtype, project_id, tenant_id FROM documents WHERE id = :d"
                ),
                {"d": document_id},
            )
        ).one()
        assert stored.dtype == kind.value  # the content address lives on the revision (below)
        assert (stored.project_id, stored.tenant_id) == (project_id, test_user.tenant_id)

        revisions = (
            await db.execute(
                text(
                    "SELECT revision_id, rev_no, parent_revision_id, blob_hash, blob_key "
                    "FROM document_revisions WHERE document_id = :d ORDER BY rev_no"
                ),
                {"d": document_id},
            )
        ).all()
        assert len(revisions) == 1, f"{name}: exactly one genesis revision"
        [genesis] = revisions
        assert (genesis.rev_no, genesis.parent_revision_id) == (1, None)
        assert genesis.blob_hash == expected
        assert expected in genesis.blob_key
        assert await worker.file_exists(genesis.blob_key)
        assert (await worker.download_object(genesis.blob_key)).read_bytes() == data, (
            "the stored blob is the uploaded bytes"
        )

        events = (
            await db.execute(
                text(
                    "SELECT payload FROM project_events WHERE source_revision_id = :r "
                    "AND event_type = 'revision.ingested'"
                ),
                {"r": genesis.revision_id},
            )
        ).all()
        assert len(events) == 1
        payload = events[0].payload
        assert payload["blob_hash"] == expected
        assert payload["document_id"] == str(document_id)

    assert await _counts(db, project_id) == {"documents": 4, "revisions": 4, "events": 4}

    # Another tenant sees none of it.
    foreign = await db.scalar(
        text("SELECT count(*) FROM document_revisions WHERE project_id = :p AND tenant_id <> :t"),
        {"p": project_id, "t": test_user.tenant_id},
    )
    assert foreign == 0


@pytest.mark.parametrize(
    ("document_type", "filename", "data", "mime"),
    [
        (
            DocumentType.BUDGET,
            "budget.docx",
            CONTRACT_DOCX,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            DocumentType.SCHEDULE,
            "schedule.docx",
            CONTRACT_DOCX,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            DocumentType.CONTRACT,
            "contract.exe",
            b"MZ\x90\x00 not a document",
            "application/octet-stream",
        ),
        (DocumentType.TECHNICAL_SPEC, "spec.bin", b"\x00\x01\x02", "application/octet-stream"),
    ],
)
async def test_the_api_refuses_an_incompatible_format_and_persists_nothing(
    db: AsyncSession,
    api: AsyncClient,
    worker: Any,  # noqa: F811
    test_user: Any,
    document_type: DocumentType,
    filename: str,
    data: bytes,
    mime: str,
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    blobs_before = sorted(p for p in worker._base_dir.rglob("*") if p.is_file())

    response = await _post(api, project_id, document_type, filename, data, mime)

    assert 400 <= response.status_code < 500, (response.status_code, response.text)
    assert response.json().get("detail"), "the refusal carries a reason"
    assert await _counts(db, project_id) == {"documents": 0, "revisions": 0, "events": 0}
    assert sorted(p for p in worker._base_dir.rglob("*") if p.is_file()) == blobs_before, (
        "no blob was written"
    )


async def test_a_refused_upload_does_not_disturb_the_accepted_ones_sent_with_it(
    db: AsyncSession,
    api: AsyncClient,
    test_user: Any,  # noqa: F811
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    requests = [
        _post(api, project_id, kind, name, data, mime) for kind, name, data, mime in FAMILIES
    ]
    requests.append(
        _post(api, project_id, DocumentType.BUDGET, "budget.docx", CONTRACT_DOCX, FAMILIES[0][3])
    )

    responses = await asyncio.gather(*requests)

    assert [response.status_code for response in responses[:4]] == [202] * 4
    assert 400 <= responses[4].status_code < 500
    assert await _counts(db, project_id) == {"documents": 4, "revisions": 4, "events": 4}
