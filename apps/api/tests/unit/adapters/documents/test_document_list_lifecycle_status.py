"""Documents list exposes an honest per-document lifecycle state (F-DOC-1).

The polling ``status`` has four values and collapses ``analyzed`` into ``parsed`` and
``parsed_pending_analysis`` into ``processing``, so the Documents UI labelled every parsed
document "Analyzed" whether or not analysis had run. ``lifecycle_status`` is additive and
keeps the six user-meaningful states apart; ``status`` is unchanged for polling clients.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.documents.adapters.http.router import get_list_documents_use_case
from src.documents.adapters.http.router import router as documents_router
from src.documents.domain.models import Document, DocumentStatus, DocumentType

EXPECTED = {
    DocumentStatus.UPLOADED: ("queued", "uploaded"),
    DocumentStatus.QUEUED: ("processing", "uploaded"),
    DocumentStatus.PARSING: ("processing", "processing"),
    DocumentStatus.PARSED: ("parsed", "parsed"),
    DocumentStatus.PARSED_PENDING_ANALYSIS: ("processing", "analysis_pending"),
    DocumentStatus.ANALYZED: ("parsed", "analyzed"),
    DocumentStatus.ERROR: ("error", "error"),
}


class _FakeListUseCase:
    def __init__(self, documents: list[Document]) -> None:
        self._documents = documents

    async def execute(self, **_: object) -> tuple[list[Document], int]:
        return self._documents, len(self._documents)


def _document(project_id, stored: DocumentStatus) -> Document:
    return Document(
        id=uuid4(),
        project_id=project_id,
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename=f"{stored.value}.pdf",
        upload_status=stored,
        file_format="pdf",
        storage_url=None,
        storage_encrypted=True,
        file_size_bytes=10,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        clauses=[],
    )


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def app(project_id) -> FastAPI:
    from src.core.security import get_current_tenant_id, get_current_user_id_with_bearer

    documents = [_document(project_id, stored) for stored in EXPECTED]
    app_obj = FastAPI()
    app_obj.include_router(documents_router)
    app_obj.dependency_overrides[get_current_tenant_id] = lambda: uuid4()
    app_obj.dependency_overrides[get_current_user_id_with_bearer] = lambda: uuid4()
    app_obj.dependency_overrides[get_list_documents_use_case] = lambda: _FakeListUseCase(documents)
    return app_obj


def test_every_stored_status_maps_to_a_distinct_honest_lifecycle_state(app, project_id) -> None:
    assert set(EXPECTED) == set(DocumentStatus), "a new DocumentStatus needs an explicit lifecycle mapping"
    response = TestClient(app).get(f"/projects/{project_id}/documents")

    assert response.status_code == 200
    by_filename = {item["filename"]: item for item in response.json()["items"]}
    for stored, (polling, lifecycle) in EXPECTED.items():
        item = by_filename[f"{stored.value}.pdf"]
        assert (item["status"], item["lifecycle_status"]) == (polling, lifecycle), stored


def test_openapi_documents_the_lifecycle_enum(app) -> None:
    schemas = app.openapi()["components"]["schemas"]
    item = schemas["DocumentListItem"]

    assert "lifecycle_status" in item["required"]
    ref = item["properties"]["lifecycle_status"]["$ref"].rsplit("/", 1)[-1]
    assert schemas[ref]["enum"] == [
        "uploaded",
        "processing",
        "parsed",
        "analysis_pending",
        "analyzed",
        "error",
    ]
