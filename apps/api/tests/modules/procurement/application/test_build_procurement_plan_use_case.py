"""
TS-I9-PROC-UC-003

Tests for BuildProcurementPlanUseCase.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.procurement.application.dtos import PlanningDecision
from src.procurement.application.use_cases.build_procurement_plan_use_case import (
    BuildProcurementPlanUseCase,
)


@pytest.mark.asyncio
async def test_execute_delegates_to_planning_service_with_tenant_scoped_inputs() -> None:
    """Use case should forward project, tenant, and target date to the planning service."""
    service = MagicMock()
    service.build_procurement_plan = AsyncMock(
        return_value=PlanningDecision(
            plan_fingerprint="f" * 64,
            conflicts=[],
            requires_human_review=False,
        )
    )
    project_id = uuid4()
    tenant_id = uuid4()
    required_on_site = date(2026, 9, 1)

    decision = await BuildProcurementPlanUseCase(planning_service=service).execute(
        project_id=project_id,
        tenant_id=tenant_id,
        required_on_site=required_on_site,
    )

    assert decision.plan_fingerprint == "f" * 64
    service.build_procurement_plan.assert_awaited_once_with(
        project_id=project_id,
        tenant_id=tenant_id,
        required_on_site=required_on_site,
    )
