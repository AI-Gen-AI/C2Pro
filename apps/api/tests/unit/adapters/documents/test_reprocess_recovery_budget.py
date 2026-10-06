"""#711 explicit Retry resets the automatic recovery budget."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.core.processing_authority import ProcessingAuthorityLost
from src.documents.adapters.http import router
from src.documents.domain.models import Document, DocumentStatus, DocumentType


@pytest.mark.asyncio
async def test_reprocess_clears_only_processing_recovery_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.ERROR,
        document_metadata={
            "processing_recovery": {
                "stage": DocumentStatus.PARSING.value,
                "generation": "v1:legacy",
                "attempts": 3,
            },
            "business_metadata": "preserve-me",
        },
    )

    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)

    async def _update_status(_tenant_id, _document_id, status, **_kwargs):
        document.upload_status = status

    async def _update_metadata(_tenant_id, _document_id, metadata):
        document.document_metadata = metadata

    repo.update_status = AsyncMock(side_effect=_update_status)
    repo.update_metadata = AsyncMock(side_effect=_update_metadata)
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    repo.begin_processing_generation = AsyncMock(return_value=2)
    enqueued: list[int | None] = []
    monkeypatch.setattr(
        router,
        "_enqueue_document_processing",
        lambda _document_id, generation=None: enqueued.append(generation) or "retry-task",
    )

    response = await router.reprocess_document_endpoint(
        project_id=project_id,
        document_id=document_id,
        user_id=uuid4(),
        tenant_id=tenant_id,
        repo=repo,
        pending_review_lookup=lambda _tenant_id, _document_ids: {},
    )

    repo.update_metadata.assert_awaited_once_with(
        tenant_id,
        document_id,
        {"business_metadata": "preserve-me"},
    )
    assert response.task_id == "retry-task"
    assert document.document_metadata == {"business_metadata": "preserve-me"}
    # #711: an explicit reprocess supersedes every earlier processing attempt.
    repo.begin_processing_generation.assert_awaited_once_with(tenant_id, document_id)
    assert enqueued == [2]



@pytest.mark.asyncio
async def test_failed_retryable_analysis_is_allowed_to_reprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        document_metadata={"analysis_last_attempt_incomplete": True},
    )
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)

    async def _update_status(_tenant_id, _document_id, new_status, **_kwargs):
        document.upload_status = new_status

    repo.update_status = AsyncMock(side_effect=_update_status)
    repo.update_metadata = AsyncMock()
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    repo.begin_processing_generation = AsyncMock(return_value=3)
    monkeypatch.setattr(
        router,
        "_enqueue_document_processing",
        lambda _document_id, generation=None: "retry-analysis",
    )

    response = await router.reprocess_document_endpoint(
        project_id=project_id,
        document_id=document_id,
        user_id=uuid4(),
        tenant_id=tenant_id,
        repo=repo,
        pending_review_lookup=lambda _tenant_id, _document_ids: {},
    )

    assert response.task_id == "retry-analysis"
    repo.update_status.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stored_status", "metadata", "pending_reviews", "expected_lifecycle"),
    [
        (DocumentStatus.UPLOADED, {}, {}, "uploaded"),
        (DocumentStatus.PARSING, {}, {}, "processing"),
        (DocumentStatus.PARSED, {}, {}, "parsed"),
        (
            DocumentStatus.PARSED_PENDING_ANALYSIS,
            {},
            {},
            "analysis_pending",
        ),
        (
            DocumentStatus.PARSED_PENDING_ANALYSIS,
            {},
            "pending",
            "review_required",
        ),
        (DocumentStatus.ANALYZED, {}, {}, "analyzed"),
        (DocumentStatus.NEEDS_CHANGES, {}, {}, "needs_changes"),
    ],
)
async def test_reprocess_rejects_every_non_retryable_lifecycle_without_mutation(
    stored_status: DocumentStatus,
    metadata: dict,
    pending_reviews: object,
    expected_lifecycle: str,
) -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=stored_status,
        document_metadata=metadata,
    )
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.update_status = AsyncMock()
    repo.update_metadata = AsyncMock()
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()

    pending_lookup = (
        {document_id: (1, uuid4())} if pending_reviews == "pending" else {}
    )

    with pytest.raises(router.HTTPException) as exc_info:
        await router.reprocess_document_endpoint(
            project_id=project_id,
            document_id=document_id,
            user_id=uuid4(),
            tenant_id=tenant_id,
            repo=repo,
            pending_review_lookup=lambda _tenant_id, _document_ids: pending_lookup,
        )

    assert exc_info.value.status_code == 409
    assert expected_lifecycle in str(exc_info.value.detail)
    repo.update_status.assert_not_awaited()
    repo.update_metadata.assert_not_awaited()
    repo.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reprocess_expected_revision_is_cas_bound_and_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    expected_revision_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.ERROR,
    )
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.lock_document_for_update = AsyncMock()
    repo.update_status = AsyncMock()
    repo.update_metadata = AsyncMock()
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    repo.begin_processing_generation = AsyncMock(return_value=7)

    revision_repo = Mock()
    revision_repo.lock_lineage = AsyncMock()
    revision_repo.get_current = AsyncMock(
        return_value=SimpleNamespace(revision_id=expected_revision_id)
    )

    enqueued: list[tuple[object, object, object]] = []
    monkeypatch.setattr(
        router,
        "_enqueue_document_processing",
        lambda document_id, revision_id=None, generation=None: (
            enqueued.append((document_id, revision_id, generation)) or "retry-cas"
        ),
    )

    response = await router.reprocess_document_endpoint(
        project_id=project_id,
        document_id=document_id,
        expected_revision_id=expected_revision_id,
        user_id=uuid4(),
        tenant_id=tenant_id,
        repo=repo,
        revision_repo=revision_repo,
        pending_review_lookup=lambda _tenant_id, _document_ids: {},
    )

    revision_repo.lock_lineage.assert_awaited_once_with(document_id, tenant_id)
    repo.lock_document_for_update.assert_awaited_once_with(tenant_id, document_id)
    revision_repo.get_current.assert_awaited_once_with(document_id, tenant_id)
    repo.begin_processing_generation.assert_awaited_once_with(
        tenant_id,
        document_id,
        expected_revision_id=expected_revision_id,
    )
    assert enqueued == [(document_id, expected_revision_id, 7)]
    assert response.task_id == "retry-cas"


@pytest.mark.asyncio
async def test_reprocess_processing_authority_mismatch_fails_before_mutation() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    expected_revision_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.ERROR,
    )
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.lock_document_for_update = AsyncMock()
    repo.update_status = AsyncMock()
    repo.update_metadata = AsyncMock()
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    repo.begin_processing_generation = AsyncMock(
        side_effect=ProcessingAuthorityLost("processing revision changed")
    )

    revision_repo = Mock()
    revision_repo.lock_lineage = AsyncMock()
    revision_repo.get_current = AsyncMock(
        return_value=SimpleNamespace(revision_id=expected_revision_id)
    )

    with pytest.raises(router.HTTPException) as exc_info:
        await router.reprocess_document_endpoint(
            project_id=project_id,
            document_id=document_id,
            expected_revision_id=expected_revision_id,
            user_id=uuid4(),
            tenant_id=tenant_id,
            repo=repo,
            revision_repo=revision_repo,
            pending_review_lookup=lambda _tenant_id, _document_ids: {},
        )

    assert exc_info.value.status_code == 409
    assert "processing authority changed" in str(exc_info.value.detail).lower()
    repo.begin_processing_generation.assert_awaited_once_with(
        tenant_id,
        document_id,
        expected_revision_id=expected_revision_id,
    )
    repo.update_metadata.assert_not_awaited()
    repo.update_status.assert_not_awaited()
    repo.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reprocess_expected_revision_mismatch_fails_before_mutation() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    expected_revision_id = uuid4()
    actual_revision_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.ERROR,
    )
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.lock_document_for_update = AsyncMock()
    repo.update_status = AsyncMock()
    repo.update_metadata = AsyncMock()
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    repo.begin_processing_generation = AsyncMock()

    revision_repo = Mock()
    revision_repo.lock_lineage = AsyncMock()
    revision_repo.get_current = AsyncMock(
        return_value=SimpleNamespace(revision_id=actual_revision_id)
    )

    with pytest.raises(router.HTTPException) as exc_info:
        await router.reprocess_document_endpoint(
            project_id=project_id,
            document_id=document_id,
            expected_revision_id=expected_revision_id,
            user_id=uuid4(),
            tenant_id=tenant_id,
            repo=repo,
            revision_repo=revision_repo,
            pending_review_lookup=lambda _tenant_id, _document_ids: {},
        )

    assert exc_info.value.status_code == 409
    assert "revision changed" in str(exc_info.value.detail).lower()
    repo.update_status.assert_not_awaited()
    repo.begin_processing_generation.assert_not_awaited()
    repo.commit.assert_not_awaited()
