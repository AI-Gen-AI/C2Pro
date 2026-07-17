"""
Get RACI matrix use case tests.

Refers to Suite ID: TS-UA-STK-UC-002.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.procurement.domain.models import WBSItem
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase
from src.stakeholders.domain.models import (
    InterestLevel,
    PowerLevel,
    RaciAssignment,
    RACIRole,
    Stakeholder,
    StakeholderQuadrant,
)


@pytest.mark.asyncio
async def test_get_raci_matrix_use_case_includes_timeline_sequence_and_schedule_dates() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    first_task_id = uuid4()
    second_task_id = uuid4()
    stakeholder_id = uuid4()

    stakeholder_repo = AsyncMock()
    wbs_repo = AsyncMock()
    project_repo = AsyncMock()

    project_repo.exists_by_id.return_value = True
    wbs_repo.get_by_project.return_value = [
        WBSItem(
            id=first_task_id,
            project_id=project_id,
            code="1.2",
            name="Permit Control",
            level=2,
            planned_start=datetime(2026, 4, 7, 0, 0, 0),
            planned_end=datetime(2026, 4, 11, 0, 0, 0),
        ),
        WBSItem(
            id=second_task_id,
            project_id=project_id,
            code="1.1",
            name="Funding Review",
            level=2,
            planned_start=datetime(2026, 4, 2, 0, 0, 0),
            planned_end=datetime(2026, 4, 5, 0, 0, 0),
        ),
    ]
    stakeholder_repo.list_raci_assignments.return_value = [
        RaciAssignment(
            id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            stakeholder_id=stakeholder_id,
            wbs_item_id=first_task_id,
            raci_role=RACIRole.ACCOUNTABLE,
            created_at=datetime(2026, 4, 1, 12, 0, 0),
        )
    ]
    stakeholder_repo.get_by_id.return_value = Stakeholder(
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

    use_case = GetRaciMatrixUseCase(
        stakeholder_repository=stakeholder_repo,
        wbs_repository=wbs_repo,
        project_repository=project_repo,
    )

    response = await use_case.execute(project_id=project_id, tenant_id=tenant_id)

    stakeholder_repo.list_raci_assignments.assert_awaited_once_with(project_id, tenant_id=tenant_id)
    stakeholder_repo.get_by_id.assert_awaited_once_with(stakeholder_id, tenant_id=tenant_id)
    assert [row.task_name for row in response.matrix] == ["Funding Review", "Permit Control"]
    assert response.matrix[0].sequence_index == 1
    assert response.matrix[0].task_code == "1.1"
    assert response.matrix[0].planned_start == datetime(2026, 4, 2, 0, 0, 0)
    assert response.matrix[0].planned_end == datetime(2026, 4, 5, 0, 0, 0)
    assert response.matrix[1].sequence_index == 2
    assert response.matrix[1].task_code == "1.2"
    assert response.matrix[1].planned_start == datetime(2026, 4, 7, 0, 0, 0)
    assert response.matrix[1].planned_end == datetime(2026, 4, 11, 0, 0, 0)
