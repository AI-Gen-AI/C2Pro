"""
Bulk Operations E2E Tests (TDD - RED Phase)

Refers to Suite ID: TS-E2E-FLW-BLK-001.
"""

from __future__ import annotations

from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_bulk_wbs_operations(client, get_auth_headers):
    """
    Bulk create/update/delete WBS items.
    """
    headers = await get_auth_headers()

    # 1) Create project
    project_payload = {
        "name": "Bulk Ops Project",
        "description": "Bulk WBS operations",
        "code": "BLK-001",
        "project_type": "construction",
        "estimated_budget": 50000.0,
        "currency": "EUR",
        "start_date": datetime.utcnow().isoformat(),
        "end_date": datetime.utcnow().isoformat(),
    }
    project_response = await client.post("/projects", json=project_payload, headers=headers)
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    # 2) Bulk create WBS items
    create_payload = {
        "project_id": project_id,
        "items": [
            {"code": "1", "name": "Root", "level": 1},
            {"code": "1.1", "name": "Child", "level": 2, "parent_code": "1"},
        ],
    }
    create_response = await client.post(
        "/v0/procurement/wbs/bulk",
        json=create_payload,
        headers=headers,
    )
    assert create_response.status_code == 201
    created_items = create_response.json()
    assert len(created_items) == 2

    # 3) Bulk update WBS items
    update_payload = {
        "project_id": project_id,
        "items": [
            {"code": "1", "name": "Root Updated", "level": 1},
            {"code": "1.1", "name": "Child Updated", "level": 2, "parent_code": "1"},
        ],
    }
    update_response = await client.put(
        "/v0/procurement/wbs/bulk",
        json=update_payload,
        headers=headers,
    )
    assert update_response.status_code == 200

    # 4) Bulk delete WBS items
    delete_payload = {"project_id": project_id, "codes": ["1", "1.1"]}
    delete_response = await client.delete(
        "/v0/procurement/wbs/bulk",
        json=delete_payload,
        headers=headers,
    )
    assert delete_response.status_code == 200
