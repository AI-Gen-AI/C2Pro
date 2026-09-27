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

from src.documents.adapters.http.router import (
    get_list_documents_use_case,
    get_pending_review_document_ids,
)
from src.documents.adapters.http.router import router as documents_router
from src.documents.domain.models import Document, DocumentStatus, DocumentType

EXPECTED = {
    DocumentStatus.UPLOADED: ("queued", "uploaded"),
    DocumentStatus.QUEUED: ("processing", "uploaded"),
    DocumentStatus.PARSING: ("processing", "processing"),
    DocumentStatus.PARSED: ("parsed", "parsed"),
    DocumentStatus.PARSED_PENDING_ANALYSIS: ("processing", "analysis_pending"),
    DocumentStatus.ANALYZED: ("parsed", "analyzed"),
    DocumentStatus.NEEDS_CHANGES: ("error", "needs_changes"),
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
    # Default: no HITL context wired up. Tests that care about the
    # context-sensitive branch override this dependency themselves.
    app_obj.dependency_overrides[get_pending_review_document_ids] = lambda: (
        lambda tenant_id, document_ids: {}
    )
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
        "review_required",
        "analyzed",
        "needs_changes",
        "failed_retryable",
        "error",
    ]


class _FakeListUseCaseWithContext:
    """Returns one PARSED_PENDING_ANALYSIS document plus whatever HITL/failure
    context the test wires up, so the router's context-sensitive branch (not
    just the context-free 1:1 mapping above) is exercised end to end."""

    def __init__(self, document: Document) -> None:
        self._document = document

    async def execute(self, **_: object) -> tuple[list[Document], int]:
        return [self._document], 1


def test_review_required_is_never_rendered_as_analysis_not_started(app, project_id) -> None:
    """A document whose analysis paused for a pending HITL review must say so --
    never "Analysis has not started", the exact false claim #712 forbids."""
    from src.documents.adapters.http.router import get_pending_review_document_ids

    document = _document(project_id, DocumentStatus.PARSED_PENDING_ANALYSIS)
    app.dependency_overrides[get_list_documents_use_case] = lambda: _FakeListUseCaseWithContext(
        document
    )
    app.dependency_overrides[get_pending_review_document_ids] = lambda: (
        lambda tenant_id, document_ids: {document.id: (1, uuid4())}
    )

    response = TestClient(app).get(f"/projects/{project_id}/documents")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["lifecycle_status"] == "review_required"
    assert item["status_detail"].lower() != "analysis has not started"
    assert "not started" not in item["status_detail"].lower()
    assert item["retryable"] is False


def test_multiple_pending_reviews_expose_a_count_not_a_guessed_item(app, project_id) -> None:
    from src.documents.adapters.http.router import get_pending_review_document_ids

    document = _document(project_id, DocumentStatus.PARSED_PENDING_ANALYSIS)
    app.dependency_overrides[get_list_documents_use_case] = lambda: _FakeListUseCaseWithContext(
        document
    )
    app.dependency_overrides[get_pending_review_document_ids] = lambda: (
        lambda tenant_id, document_ids: {document.id: (2, None)}
    )

    response = TestClient(app).get(f"/projects/{project_id}/documents")

    item = response.json()["items"][0]
    assert item["lifecycle_status"] == "review_required"
    assert item["review_count"] == 2
    assert item.get("review_item_id") is None


def test_single_pending_review_exposes_the_exact_item_id(app, project_id) -> None:
    from src.documents.adapters.http.router import get_pending_review_document_ids

    document = _document(project_id, DocumentStatus.PARSED_PENDING_ANALYSIS)
    review_item_id = uuid4()
    app.dependency_overrides[get_list_documents_use_case] = lambda: _FakeListUseCaseWithContext(
        document
    )
    app.dependency_overrides[get_pending_review_document_ids] = lambda: (
        lambda tenant_id, document_ids: {document.id: (1, review_item_id)}
    )

    response = TestClient(app).get(f"/projects/{project_id}/documents")

    item = response.json()["items"][0]
    assert item["lifecycle_status"] == "review_required"
    assert item["review_count"] == 1
    assert item["review_item_id"] == str(review_item_id)


def test_exhausted_retry_is_distinguishable_from_active_analysis(app, project_id) -> None:
    """An analysis attempt that ran and came back incomplete must not look
    identical to "queued, hasn't started yet" -- and must offer retry."""
    document = _document(project_id, DocumentStatus.PARSED_PENDING_ANALYSIS)
    document.document_metadata = {"analysis_last_attempt_incomplete": True}
    app.dependency_overrides[get_list_documents_use_case] = lambda: _FakeListUseCaseWithContext(
        document
    )

    response = TestClient(app).get(f"/projects/{project_id}/documents")

    item = response.json()["items"][0]
    assert item["lifecycle_status"] == "failed_retryable"
    assert item["retryable"] is True


def test_needs_changes_is_retryable_false_and_stops_looking_like_processing(
    app, project_id
) -> None:
    document = _document(project_id, DocumentStatus.NEEDS_CHANGES)
    app.dependency_overrides[get_list_documents_use_case] = lambda: _FakeListUseCaseWithContext(
        document
    )

    response = TestClient(app).get(f"/projects/{project_id}/documents")

    item = response.json()["items"][0]
    assert item["lifecycle_status"] == "needs_changes"
    assert item["status"] != "processing"
    assert item["retryable"] is False
