"""TS-UA-STK-UC-001 / TASK-BCK-095: stakeholder approval review tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.approval import ApprovalStatus
from src.stakeholders.application.review_stakeholder_approval_use_case import (
    ReviewStakeholderApprovalUseCase,
)
from src.stakeholders.domain.models import InterestLevel, PowerLevel, Stakeholder


@pytest.mark.asyncio
async def test_review_stakeholder_approval_forwards_tenant_to_repository_calls() -> None:
    tenant_id = uuid4()
    stakeholder_id = uuid4()
    now = datetime.now(UTC)
    stakeholder = Stakeholder(
        id=stakeholder_id,
        project_id=uuid4(),
        tenant_id=tenant_id,
        power_level=PowerLevel.HIGH,
        interest_level=InterestLevel.HIGH,
        approval_status=ApprovalStatus.PENDING,
        created_at=now,
        updated_at=now,
        name="Tenant-isolated reviewer",
    )
    repository = AsyncMock()
    repository.get_by_id.return_value = stakeholder
    use_case = ReviewStakeholderApprovalUseCase(repository=repository)

    reviewed, _ = await use_case.execute(
        tenant_id=tenant_id,
        stakeholder_id=stakeholder_id,
        status=ApprovalStatus.APPROVED,
        correction_data=None,
        feedback_comment=None,
        user_id=uuid4(),
    )

    repository.get_by_id.assert_awaited_once_with(stakeholder_id, tenant_id)
    repository.update.assert_awaited_once_with(stakeholder, tenant_id)
    assert reviewed is stakeholder
