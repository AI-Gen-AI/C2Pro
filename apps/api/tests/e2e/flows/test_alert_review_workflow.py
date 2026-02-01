"""
Alert Review Workflow E2E Tests (TDD - RED Phase)

Refers to Suite ID: TS-E2E-FLW-ALR-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_alert_review_workflow(client, get_auth_headers):
    """
    End-to-end alert review: create -> list -> approve -> evidence.
    """
    headers = await get_auth_headers()
    project_id = str(uuid4())
    clause_id = str(uuid4())

    # 1) Create/trigger alert
    create_payload = {
        "project_id": project_id,
        "clause_id": clause_id,
        "category": "LEGAL",
        "severity": "critical",
        "message": "Penalty clause without milestone.",
        "source": "system",
    }
    create_response = await client.post(
        "/v0/analysis/alerts",
        json=create_payload,
        headers=headers,
    )
    assert create_response.status_code == 201
    alert_id = create_response.json()["id"]

    # 2) List alerts for review (active + high/critical)
    list_response = await client.get(
        f"/v0/analysis/alerts?project_id={project_id}&status=active&severity=high,critical",
        headers=headers,
    )
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["id"] == alert_id for item in items)

    # 3) Approve alert
    approve_response = await client.post(
        f"/v0/analysis/alerts/{alert_id}/approve",
        headers=headers,
    )
    assert approve_response.status_code == 200

    # 4) Evidence view for clause
    evidence_response = await client.get(
        f"/api/evidence/{clause_id}",
        headers=headers,
    )
    assert evidence_response.status_code == 200
