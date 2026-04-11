"""
TS-UAD-HTTP-RTR-001: Alerts route contract compatibility tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.projects.adapters.persistence.models import ProjectORM


@pytest.mark.asyncio
async def test_canonical_project_alerts_route_remains_supported(
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Alerts Contract Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    response = await client.get(
        f"/api/v1/projects/{project.id}/alerts",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
