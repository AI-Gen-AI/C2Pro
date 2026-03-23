"""
TS-INT-DB-CLS-001: Document entities contract tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.domain.models import ClauseType, DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM


@pytest.mark.asyncio
async def test_document_entities_route_returns_clause_derived_entities(
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Evidence Project",
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
        storage_url="/tmp/contract.pdf",
        file_format="pdf",
        file_size_bytes=10,
        upload_status=DocumentStatus.PARSED,
    )
    db.add(document)
    await db.flush()

    clause = ClauseORM(
        id=uuid4(),
        project_id=project.id,
        document_id=document.id,
        clause_code="1.1",
        clause_type=ClauseType.PAYMENT,
        title="Payment Terms",
        full_text="Payment shall be made within 30 days.",
        extraction_confidence=0.92,
        extracted_entities={
            "evidence_location": {
                "page_number": 3,
                "bbox": [0.1, 0.2, 0.5, 0.08],
                "normalized": True,
            }
        },
    )
    db.add(clause)
    await db.commit()

    response = await client.get(
        f"/api/v1/documents/{document.id}/entities",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(clause.id)
    assert body[0]["type"] == "clause"
    assert body[0]["text"] == "Payment Terms"
    assert body[0]["page"] == 3
    assert body[0]["confidence"] == 0.92
    assert body[0]["metadata"]["evidence_location"]["bbox"] == [0.1, 0.2, 0.5, 0.08]
