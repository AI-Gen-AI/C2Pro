"""PQ-HITL-03: revision status inspection is read-only and tenant-scoped."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.documents.adapters.http.router import list_document_revision_statuses_endpoint
from src.temporal.application.revision_status import RevisionStatus


@pytest.mark.asyncio
async def test_lists_proposed_revision_without_making_it_trusted_current() -> None:
    tenant_id, document_id, project_id, user_id, revision_id = (uuid4() for _ in range(5))
    revision = SimpleNamespace(
        revision_id=revision_id,
        document_id=document_id,
        tenant_id=tenant_id,
        project_id=project_id,
        rev_no=2,
        created_at=datetime.now(UTC),
    )
    document_lookup = MagicMock()
    document_lookup.execute = AsyncMock(return_value=SimpleNamespace(project_id=project_id))
    revisions = MagicMock()
    revisions.list_lineage = AsyncMock(return_value=[revision])
    expected = RevisionStatus(
        revision_id=revision_id,
        rev_no=2,
        trust_state="proposed",
        is_current=False,
        current_basis="unresolved",
    )
    reader = MagicMock()
    reader.read = AsyncMock(return_value=expected)

    with patch(
        "src.documents.adapters.http.router.SqlAlchemyRevisionStatusReader",
        return_value=reader,
    ):
        result = await list_document_revision_statuses_endpoint(
            document_id=document_id,
            _user_id=user_id,
            tenant_id=tenant_id,
            get_document=document_lookup,
            revision_repository=revisions,
            db=MagicMock(),
        )

    assert result == [expected]
    assert result[0].is_current is False
    assert result[0].trust_state == "proposed"
    document_lookup.execute.assert_awaited_once_with(document_id, user_id, tenant_id)
    revisions.list_lineage.assert_awaited_once_with(document_id, tenant_id)
    reader.read.assert_awaited_once_with(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
    )


@pytest.mark.asyncio
async def test_missing_document_never_reads_other_tenant_lineage() -> None:
    tenant_id, document_id, user_id = uuid4(), uuid4(), uuid4()
    document_lookup = MagicMock()
    document_lookup.execute = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Document not found.")
    )
    revisions = MagicMock()
    revisions.list_lineage = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await list_document_revision_statuses_endpoint(
            document_id=document_id,
            _user_id=user_id,
            tenant_id=tenant_id,
            get_document=document_lookup,
            revision_repository=revisions,
            db=MagicMock(),
        )

    assert error.value.status_code == 404
    revisions.list_lineage.assert_not_awaited()


@pytest.mark.asyncio
async def test_corrupted_cross_project_revision_fails_closed() -> None:
    tenant_id, document_id, project_id, user_id, revision_id = (uuid4() for _ in range(5))
    doc = MagicMock()
    doc.execute = AsyncMock(return_value=SimpleNamespace(project_id=project_id))
    revs = MagicMock()
    revs.list_lineage = AsyncMock(
        return_value=[
            SimpleNamespace(
                revision_id=revision_id,
                document_id=document_id,
                tenant_id=tenant_id,
                project_id=uuid4(),
            )
        ]
    )

    with pytest.raises(HTTPException) as error:
        await list_document_revision_statuses_endpoint(
            document_id=document_id,
            _user_id=user_id,
            tenant_id=tenant_id,
            get_document=doc,
            revision_repository=revs,
            db=MagicMock(),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_unavailable_revision_status_never_becomes_trusted() -> None:
    tenant_id, document_id, project_id, user_id, revision_id = (uuid4() for _ in range(5))
    lookup = MagicMock()
    lookup.execute = AsyncMock(return_value=SimpleNamespace(project_id=project_id))
    revisions = MagicMock()
    revisions.list_lineage = AsyncMock(
        return_value=[
            SimpleNamespace(
                revision_id=revision_id,
                document_id=document_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
        ]
    )
    reader = MagicMock()
    reader.read = AsyncMock(return_value=None)

    with patch(
        "src.documents.adapters.http.router.SqlAlchemyRevisionStatusReader",
        return_value=reader,
    ):
        results = await list_document_revision_statuses_endpoint(
            document_id=document_id,
            _user_id=user_id,
            tenant_id=tenant_id,
            get_document=lookup,
            revision_repository=revisions,
            db=MagicMock(),
        )

    assert results[0].status == "unavailable"
    assert results[0].trust_state is None
    assert results[0].is_current is False
