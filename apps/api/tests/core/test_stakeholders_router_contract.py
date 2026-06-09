"""
TS-INT-DB-CLS-001: Stakeholders API contract tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.approval import ApprovalStatus
from src.projects.adapters.persistence.models import ProjectORM
from src.stakeholders.adapters.persistence.models import StakeholderORM
from src.stakeholders.domain.models import InterestLevel, PowerLevel, StakeholderQuadrant


@pytest.mark.asyncio
async def test_project_scoped_stakeholders_route_returns_project_stakeholders(
    client,
    db,
    test_tenant,
    test_tenant_2,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Project A",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    other_project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        name="Project B",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add_all([project, other_project])
    await db.flush()

    db.add_all(
        [
            StakeholderORM(
                tenant_id=test_tenant.id,
                project_id=project.id,
                name="Ana Ruiz",
                role="PM",
                power_level=PowerLevel.HIGH,
                interest_level=InterestLevel.HIGH,
                quadrant=StakeholderQuadrant.KEY_PLAYER,
                approval_status=ApprovalStatus.PENDING,
                stakeholder_metadata={},
            ),
            StakeholderORM(
                tenant_id=test_tenant_2.id,
                project_id=other_project.id,
                name="Blocked Tenant User",
                role="Observer",
                power_level=PowerLevel.LOW,
                interest_level=InterestLevel.LOW,
                quadrant=StakeholderQuadrant.MONITOR,
                approval_status=ApprovalStatus.PENDING,
                stakeholder_metadata={},
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        f"/api/v1/stakeholders/projects/{project.id}",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Ana Ruiz"
