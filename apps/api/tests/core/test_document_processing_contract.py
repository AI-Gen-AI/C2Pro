"""
TS-INT-DOC-PROC-001: Document processing contract tests.
"""

from __future__ import annotations

import io
from uuid import uuid4

import pytest

from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM


@pytest.mark.asyncio
async def test_upload_response_exposes_non_terminal_processing_state(
    client,
    db,
    test_tenant,
    test_user,
    generate_token,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Upload Contract Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )

    response = await client.post(
        f"/api/v1/projects/{project.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("contract.pdf", io.BytesIO(b"%PDF-1.4\nmock"), "application/pdf")},
        data={"document_type": "contract"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["processing_status"] == "queued"
    assert "analysis has not started" in payload["status_detail"].lower()


@pytest.mark.asyncio
async def test_document_list_marks_parsed_as_pre_analysis_state(
    client,
    db,
    test_tenant,
    test_user,
    generate_token,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Parsed Contract Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.flush()
    db.add(
        DocumentORM(
            id=uuid4(),
            project_id=project.id,
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            storage_url="memory://contract.pdf",
            file_format="pdf",
            file_size_bytes=42,
            upload_status=DocumentStatus.PARSED,
        )
    )
    await db.commit()

    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )

    response = await client.get(
        f"/api/v1/projects/{project.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "parsed"
    assert "triggered separately" in item["status_detail"].lower()
