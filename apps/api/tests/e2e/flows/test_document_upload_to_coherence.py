"""
Document Upload to Coherence E2E Tests (TDD - RED Phase)

Refers to Suite ID: TS-E2E-FLW-DOC-001.
"""

from __future__ import annotations

from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_document_upload_triggers_coherence_score(client, get_auth_headers):
    """
    Upload a document and verify coherence is eventually available.
    """
    headers = await get_auth_headers()

    # 1) Create project
    project_payload = {
        "name": "E2E Project",
        "description": "E2E doc to coherence flow",
        "code": "E2E-001",
        "project_type": "construction",
        "estimated_budget": 100000.0,
        "currency": "EUR",
        "start_date": datetime.utcnow().isoformat(),
        "end_date": datetime.utcnow().isoformat(),
    }
    project_response = await client.post("/projects", json=project_payload, headers=headers)
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    # 2) Upload document for processing
    files = {
        "file": ("contract.pdf", b"%PDF-1.4 fake", "application/pdf"),
    }
    data = {"document_type": "contract"}
    upload_response = await client.post(
        f"/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )
    assert upload_response.status_code == 202

    # 3) Expect coherence dashboard to reflect processed document
    coherence_response = await client.get(f"/api/coherence/dashboard/{project_id}", headers=headers)
    assert coherence_response.status_code == 200
    body = coherence_response.json()
    assert "coherence_score" in body
