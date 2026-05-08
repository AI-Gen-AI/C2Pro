"""Test Suite ID: TASK-OPS-DOCFLOW-005.

Real document upload and persistence contract for the operability gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.http.router import get_storage_service
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.domain.models import DocumentStatus
from src.projects.adapters.persistence.models import ProjectORM

CORPUS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "real"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"


def _corpus_entry(document_type: str) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(entry for entry in manifest if entry["document_type"] == document_type)


@pytest.mark.asyncio
async def test_real_pdf_upload_persists_tenant_project_storage_and_status(
    app,
    client: AsyncClient,
    db: AsyncSession,
    get_auth_headers,
    test_user,
    tmp_path: Path,
) -> None:
    entry = _corpus_entry("construction_contract")
    fixture_path = CORPUS_DIR / entry["filename"]
    headers = get_auth_headers(user=test_user)
    upload_dir = tmp_path / "real-document-uploads"
    app.dependency_overrides[get_storage_service] = lambda: LocalFileStorageService(
        base_dir=upload_dir
    )

    project_response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Real Document Upload Project",
            "project_type": "construction",
        },
        headers=headers,
    )
    assert project_response.status_code == 201, project_response.text
    project_id = UUID(project_response.json()["id"])

    try:
        with fixture_path.open("rb") as fixture_file:
            upload_response = await client.post(
                f"/api/v1/projects/{project_id}/documents",
                files={
                    "file": (
                        entry["filename"],
                        fixture_file,
                        entry["expected_upload"]["content_type"],
                    )
                },
                data={"document_type": "contract"},
                headers=headers,
            )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)

    assert upload_response.status_code == 202, upload_response.text
    payload = upload_response.json()
    document_id = UUID(payload["id"])
    assert payload["project_id"] == str(project_id)
    assert payload["upload_status"] == DocumentStatus.UPLOADED.value
    assert payload["processing_status"] == "queued"

    row = (
        await db.execute(
            select(DocumentORM, ProjectORM)
            .join(ProjectORM, ProjectORM.id == DocumentORM.project_id)
            .where(DocumentORM.id == document_id)
        )
    ).one()
    document, project = row

    assert project.tenant_id == test_user.tenant_id
    assert document.project_id == project_id
    assert document.filename == entry["filename"]
    assert document.file_format == ".pdf"
    assert document.file_size_bytes == fixture_path.stat().st_size
    assert document.upload_status == DocumentStatus.UPLOADED
    assert document.created_by == test_user.id
    assert document.storage_url is not None
    assert Path(document.storage_url).is_file()
    assert Path(document.storage_url).read_bytes() == fixture_path.read_bytes()


@pytest.mark.asyncio
async def test_real_unsupported_fixture_is_rejected_without_document_record(
    client: AsyncClient,
    db: AsyncSession,
    get_auth_headers,
    test_user,
) -> None:
    entry = _corpus_entry("unsupported")
    fixture_path = CORPUS_DIR / entry["filename"]
    headers = get_auth_headers(user=test_user)

    project_response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Unsupported Real Document Project",
            "project_type": "construction",
        },
        headers=headers,
    )
    assert project_response.status_code == 201, project_response.text
    project_id = UUID(project_response.json()["id"])

    with fixture_path.open("rb") as fixture_file:
        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            files={
                "file": (
                    entry["filename"],
                    fixture_file,
                    entry["expected_upload"]["content_type"],
                )
            },
            data={"document_type": "other"},
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "File type '.bin' is not allowed."

    document_count = (
        await db.execute(
            select(DocumentORM)
            .join(ProjectORM, ProjectORM.id == DocumentORM.project_id)
            .where(ProjectORM.id == project_id)
        )
    ).scalars().all()
    assert document_count == []
