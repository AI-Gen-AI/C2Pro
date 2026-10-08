"""PQ-HITL-03: revision-scoped evidence inventory without implicit promotion.

The case is deliberately independent of a database and uses the existing
tenant-scoped repository boundaries. Only physically bound clause rows count.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.documents.application.list_document_revision_evidence_use_case import (
    ListDocumentRevisionEvidenceUseCase,
)
from src.temporal.application.revision_status import RevisionStatus


@pytest.mark.asyncio
async def test_tenant_scoped_lineage_keeps_nine_historical_and_seven_proposed_clauses() -> None:
    tenant, document_id, project_id = uuid4(), uuid4(), uuid4()
    a_id, b_id = uuid4(), uuid4()
    document = SimpleNamespace(id=document_id, project_id=project_id, tenant_id=tenant)
    revisions = [
        SimpleNamespace(revision_id=a_id, rev_no=1, document_id=document_id, project_id=project_id, tenant_id=tenant),
        SimpleNamespace(revision_id=b_id, rev_no=2, document_id=document_id, project_id=project_id, tenant_id=tenant),
    ]
    doc_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=document),
        list_clauses_bound_to_revision=AsyncMock(
            side_effect=[[object()] * 9, [object()] * 7]
        ),
    )
    rev_repo = SimpleNamespace(list_lineage=AsyncMock(return_value=revisions))
    statuses = [
        RevisionStatus(
            revision_id=a_id, rev_no=1, trust_state=None, current_basis="unresolved",
        ),
        RevisionStatus(
            revision_id=b_id, rev_no=2, trust_state="proposed", current_basis="unresolved",
        ),
    ]
    reader = SimpleNamespace(read=AsyncMock(side_effect=statuses))
    result = await ListDocumentRevisionEvidenceUseCase(
        document_repository=doc_repo, revision_repository=rev_repo, status_reader=reader
    ).execute(tenant_id=tenant, document_id=document_id)

    assert result.document_id == document_id
    assert [(r.rev_no, r.clause_count, r.scope) for r in result.items] == [
        (1, 9, "unresolved"),
        (2, 7, "proposed"),
    ]
    assert all(not r.trusted_current for r in result.items)
    assert result.current_trusted_revision_id is None
    assert result.total_persisted_clauses == 16
    doc_repo.get_by_id.assert_awaited_once_with(tenant, document_id)
    rev_repo.list_lineage.assert_awaited_once_with(document_id, tenant)
    assert doc_repo.list_clauses_bound_to_revision.await_count == 2
    assert reader.read.await_args_list[0].kwargs == {
        "tenant_id": tenant,
        "project_id": project_id,
        "document_id": document_id,
        "revision_id": a_id,
    }


@pytest.mark.asyncio
async def test_trusted_current_is_only_explicit_revision_bound_trusted_status() -> None:
    tenant, document_id, project_id, revision_id = (uuid4() for _ in range(4))
    doc_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(
            id=document_id, project_id=project_id, tenant_id=tenant
        )),
        list_clauses_bound_to_revision=AsyncMock(return_value=[object(), object()]),
    )
    rev_repo = SimpleNamespace(
        list_lineage=AsyncMock(return_value=[SimpleNamespace(
            revision_id=revision_id, rev_no=1, tenant_id=tenant,
            document_id=document_id, project_id=project_id
        )]),
    )
    reader = SimpleNamespace(read=AsyncMock(return_value=RevisionStatus(
        revision_id=revision_id, rev_no=1,
        trust_state="trusted", is_current=True,
        current_revision_id=revision_id, current_basis="trusted",
    )))
    result = await ListDocumentRevisionEvidenceUseCase(
        document_repository=doc_repo, revision_repository=rev_repo, status_reader=reader
    ).execute(tenant_id=tenant, document_id=document_id)
    assert result.current_trusted_revision_id == revision_id
    assert result.items[0].scope == "trusted_current"
    assert result.items[0].trusted_current is True
    assert result.items[0].clause_count == 2


@pytest.mark.asyncio
async def test_nonexistent_tenant_document_fails_closed_before_lineage_read() -> None:
    tenant, document_id = uuid4(), uuid4()
    doc_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    rev_repo = SimpleNamespace(list_lineage=AsyncMock())
    reader = SimpleNamespace(read=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await ListDocumentRevisionEvidenceUseCase(
            document_repository=doc_repo,
            revision_repository=rev_repo,
            status_reader=reader
        ).execute(tenant_id=tenant, document_id=document_id)
    assert exc.value.status_code == 404
    rev_repo.list_lineage.assert_not_awaited()
    reader.read.assert_not_awaited()


@pytest.mark.asyncio
async def test_revision_status_unavailable_is_not_implicitly_trusted() -> None:
    tenant, document_id, project_id, revision_id = (uuid4() for _ in range(4))
    document = SimpleNamespace(id=document_id, tenant_id=tenant, project_id=project_id)
    revision = SimpleNamespace(
        revision_id=revision_id, rev_no=1, tenant_id=tenant,
        project_id=project_id, document_id=document_id
    )
    doc_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=document),
        list_clauses_bound_to_revision=AsyncMock(return_value=[object()]),
    )
    rev_repo = SimpleNamespace(list_lineage=AsyncMock(return_value=[revision]))
    reader = SimpleNamespace(read=AsyncMock(return_value=RevisionStatus.unavailable(
        revision_id, "revision_status_read_failed"
    )))
    result = await ListDocumentRevisionEvidenceUseCase(
        document_repository=doc_repo, revision_repository=rev_repo, status_reader=reader
    ).execute(tenant_id=tenant, document_id=document_id)
    assert result.items[0].scope == "unresolved"
    assert result.items[0].clause_count == 1
    assert result.items[0].trusted_current is False
    assert result.current_trusted_revision_id is None
