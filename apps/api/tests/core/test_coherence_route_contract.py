"""
TS-E2E-FLW-DOC-001: Coherence route contract tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.coherence.router import get_coherence_dashboard
from src.projects.adapters.persistence.models import ProjectORM


def _request_for_tenant(tenant_id):
    return SimpleNamespace(tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_canonical_coherence_dashboard_route_exists(
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Coherence Contract Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    response = await client.get(
        f"/api/v1/coherence/dashboard/{project.id}",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == str(project.id)


@pytest.mark.asyncio
async def test_legacy_coherence_dashboard_route_remains_supported(
    db,
    test_tenant,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Legacy Coherence Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    result = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert result.project_id == str(project.id)


@pytest.mark.asyncio
async def test_canonical_coherence_evaluate_route_is_registered(
    client,
    test_user,
    test_tenant,
    get_auth_headers,
) -> None:
    response = await client.post(
        "/api/v1/coherence/evaluate",
        json={},
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code != 404
