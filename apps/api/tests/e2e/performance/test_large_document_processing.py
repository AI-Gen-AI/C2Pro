"""
Large Document Processing E2E Tests (TDD - RED Phase)

Refers to Suite ID: TS-E2E-PER-LRG-001.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_large_document_upload_and_processing(client, get_auth_headers):
    """
    Upload a large document and expect it to be processed successfully.
    """
    headers = await get_auth_headers()

    # 1) Create project
    project_payload = {
        "name": "Large Doc Project",
        "description": "E2E large document processing",
        "code": "LRG-001",
        "project_type": "construction",
        "estimated_budget": 100000.0,
        "currency": "EUR",
        "start_date": datetime.utcnow().isoformat(),
        "end_date": datetime.utcnow().isoformat(),
    }
    project_response = await client.post("/projects", json=project_payload, headers=headers)
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    # 2) Upload large (but allowed) document
    large_payload = b"%PDF-1.4\n" + (b"x" * (5 * 1024 * 1024))  # ~5MB
    files = {"file": ("large_contract.pdf", large_payload, "application/pdf")}
    data = {"document_type": "contract"}
    upload_response = await client.post(
        f"/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )
    assert upload_response.status_code == 202
    document_id = upload_response.json()["id"]

    # 3) Poll document status until parsed (or timeout)
    for _ in range(5):
        doc_response = await client.get(f"/documents/{document_id}", headers=headers)
        assert doc_response.status_code == 200
        status = doc_response.json().get("upload_status") or doc_response.json().get("status")
        if status == "parsed":
            break
        await asyncio.sleep(0.5)

    assert status == "parsed"
