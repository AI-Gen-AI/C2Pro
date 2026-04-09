"""
Budget API integration tests for the live project budget alias.
Test Suite ID: TS-I9-PROC-BUDGET-001
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio

from src.procurement.adapters.persistence.models import BudgetItemORM
from src.projects.adapters.persistence.models import ProjectORM

API_PREFIX = "/api/v1/projects"


@pytest_asyncio.fixture
async def test_project(db, test_tenant):
    """Create a project in the authenticated tenant for budget API tests."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Budget API Project",
        code=f"BUD-{uuid4().hex[:6]}",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest_asyncio.fixture
async def another_tenant_project(db, test_tenant_2):
    """Create a project owned by a different tenant."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        name="Other Tenant Project",
        code=f"OTH-{uuid4().hex[:6]}",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _add_budget_item(
    db,
    *,
    project_id,
    name: str,
    code: str,
    amount: Decimal,
) -> BudgetItemORM:
    """Seed a procurement budget item directly for read-path integration tests."""
    item = BudgetItemORM(
        project_id=project_id,
        name=name,
        code=code,
        amount=amount,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


class TestBudgetAPI:
    """Integration coverage for the active project budget endpoint."""

    @pytest.mark.asyncio
    async def test_get_budget_reads_procurement_budget_items(
        self, client, db, test_project, get_auth_headers
    ):
        """GET /projects/{id}/budget should aggregate from procurement_budget_items."""
        await _add_budget_item(
            db,
            project_id=test_project.id,
            name="Steel Towers",
            code="BUD-001",
            amount=Decimal("100000.00"),
        )

        response = await client.get(
            f"{API_PREFIX}/{test_project.id}/budget",
            headers=get_auth_headers(),
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == str(test_project.id)
        assert payload["total_budget"] == 100000.0
        assert payload["remaining_budget"] == 100000.0
        assert payload["spent_amount"] == 0.0

    @pytest.mark.asyncio
    async def test_budget_respects_tenant_isolation(
        self, client, db, another_tenant_project, get_auth_headers
    ):
        """Budget alias should not expose projects owned by another tenant."""
        await _add_budget_item(
            db,
            project_id=another_tenant_project.id,
            name="Tenant 2 Item",
            code="T2-001",
            amount=Decimal("10000.00"),
        )

        response = await client.get(
            f"{API_PREFIX}/{another_tenant_project.id}/budget",
            headers=get_auth_headers(),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_budget_total_calculation_is_correct(
        self, client, db, test_project, get_auth_headers
    ):
        """Total budget should be the sum of all procurement budget items."""
        await _add_budget_item(
            db,
            project_id=test_project.id,
            name="Item 1",
            code="T1-001",
            amount=Decimal("10000.00"),
        )
        await _add_budget_item(
            db,
            project_id=test_project.id,
            name="Item 2",
            code="T1-002",
            amount=Decimal("20000.00"),
        )

        response = await client.get(
            f"{API_PREFIX}/{test_project.id}/budget",
            headers=get_auth_headers(),
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_budget"] == 30000.0
        assert payload["remaining_budget"] == 30000.0
