"""
TS-INT-DB-CLS-001: Documents parse route contract tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.documents.adapters.http.router import get_parse_document_use_case
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM


@pytest.mark.asyncio
async def test_canonical_documents_parse_route_is_available(
    app,
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Parse Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.flush()

    document = DocumentORM(
        id=uuid4(),
        project_id=project.id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        storage_url="memory://contract.pdf",
        file_format="pdf",
        file_size_bytes=10,
        upload_status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    await db.commit()

    mock_use_case = AsyncMock()
    app.dependency_overrides[get_parse_document_use_case] = lambda: mock_use_case

    response = await client.post(
        f"/api/v1/documents/{document.id}/parse",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["document_id"] == str(document.id)
    assert body["status"] == "parsed"
    mock_use_case.execute.assert_awaited_once_with(document.id, test_user.id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_legacy_parse_route_remains_backward_compatible(
    app,
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Legacy Parse Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.flush()

    document = DocumentORM(
        id=uuid4(),
        project_id=project.id,
        document_type=DocumentType.CONTRACT,
        filename="legacy.pdf",
        storage_url="/tmp/legacy.pdf",
        file_format="pdf",
        file_size_bytes=10,
        upload_status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    await db.commit()

    mock_use_case = AsyncMock()
    app.dependency_overrides[get_parse_document_use_case] = lambda: mock_use_case

    response = await client.post(
        f"/api/v1/{document.id}/parse",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 202
    mock_use_case.execute.assert_awaited_once_with(document.id, test_user.id)

    app.dependency_overrides.clear()
