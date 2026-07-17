"""
Upsert RACI assignment use case tests.

Refers to Suite ID: TS-UA-STK-UC-003.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.procurement.domain.models import WBSItem
from src.stakeholders.application.dtos import RaciAssignmentUpsertRequest
from src.stakeholders.application.upsert_raci_assignment_use_case import UpsertRaciAssignmentUseCase
from src.stakeholders.domain.models import (
    InterestLevel,
    PowerLevel,
    RACIRole,
    Stakeholder,
    StakeholderQuadrant,
)


@pytest.mark.asyncio
async def test_upsert_raci_assignment_propagates_tenant_id_to_repository_calls() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    task_id = uuid4()
    stakeholder_id = uuid4()

    stakeholder_repository = AsyncMock()
    stakeholder_repository.get_by_id.return_value = Stakeholder(
        id=stakeholder_id,
        project_id=project_id,
        tenant_id=tenant_id,
        name="Maria Gomez",
        power_level=PowerLevel.HIGH,
        interest_level=InterestLevel.HIGH,
        quadrant=StakeholderQuadrant.KEY_PLAYER,
        approval_status="approved",
        created_at=datetime(2026, 4, 1, 10, 0, 0),
        updated_at=datetime(2026, 4, 1, 10, 0, 0),
    )
    stakeholder_repository.get_accountable_assignment.return_value = None
    stakeholder_repository.get_raci_assignment.return_value = None

    wbs_repository = AsyncMock()
    wbs_repository.get_by_id.return_value = WBSItem(
        id=task_id,
        project_id=project_id,
        code="1.1",
        name="Permit Control",
        level=2,
    )

    use_case = UpsertRaciAssignmentUseCase(
        stakeholder_repository=stakeholder_repository,
        wbs_repository=wbs_repository,
    )

    response = await use_case.execute(
        tenant_id=tenant_id,
        user_id=user_id,
        payload=RaciAssignmentUpsertRequest(
            task_id=task_id,
            stakeholder_id=stakeholder_id,
            role=RACIRole.ACCOUNTABLE.value,
        ),
    )

    stakeholder_repository.get_by_id.assert_awaited_once_with(stakeholder_id, tenant_id=tenant_id)
    stakeholder_repository.get_accountable_assignment.assert_awaited_once_with(
        project_id=project_id,
        wbs_item_id=task_id,
        exclude_stakeholder_id=stakeholder_id,
        tenant_id=tenant_id,
    )
    stakeholder_repository.get_raci_assignment.assert_awaited_once_with(
        project_id=project_id,
        wbs_item_id=task_id,
        stakeholder_id=stakeholder_id,
        tenant_id=tenant_id,
    )
    stakeholder_repository.add_raci_assignment.assert_awaited_once()
    assignment = stakeholder_repository.add_raci_assignment.await_args.args[0]
    assert assignment.project_id == project_id
    assert assignment.tenant_id == tenant_id
    assert assignment.wbs_item_id == task_id
    assert stakeholder_repository.add_raci_assignment.await_args.kwargs == {"tenant_id": tenant_id}
    stakeholder_repository.commit.assert_awaited_once()
    assert response.task_id == task_id
    assert response.stakeholder_id == stakeholder_id
    assert response.role == "ACCOUNTABLE"
