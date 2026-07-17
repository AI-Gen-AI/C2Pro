"""TS-UD-HEALTH-018-006 - Project-scoped health vector API."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import TenantId, require_tenant_id
from src.health.application.health_engine import assemble_health_vector
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    HealthVector,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.ports.project_snapshot_repository import IProjectSnapshotRepository

router = APIRouter(prefix="/projects", tags=["project-health"])


async def get_snapshot_repository(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AsyncGenerator[IProjectSnapshotRepository, None]:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        yield SqlAlchemyProjectSnapshotRepository(session)


@router.get(
    "/{project_id}/health",
    response_model=HealthVector,
    summary="Get latest project health vector",
)
async def get_project_health(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[IProjectSnapshotRepository, Depends(get_snapshot_repository)],
) -> HealthVector:
    """Return latest tenant-scoped project HealthVector or honest insufficient data."""

    tenant_id = require_tenant_id(current_user.tenant_id)
    snapshot = await repository.latest(project_id, tenant_id)
    if snapshot is None:
        return _insufficient_data_vector(project_id, tenant_id)
    return HealthVector.model_validate(snapshot.health_vector)


def _insufficient_data_vector(project_id: UUID, tenant_id: TenantId) -> HealthVector:
    return assemble_health_vector(
        project_id,
        tenant_id,
        signals=[
            _unknown_signal(HealthDimension.CONTRACT, "no health snapshot available"),
            _unknown_signal(HealthDimension.RISK, "no health snapshot available"),
            _unknown_signal(HealthDimension.DOCUMENTATION, "no health snapshot available"),
            _unknown_signal(HealthDimension.GOVERNANCE, "no health snapshot available"),
        ],
        prior_composite=None,
    )


def _unknown_signal(dimension: HealthDimension, reason: str) -> HealthSignal:
    return HealthSignal(
        dimension=dimension,
        score=None,
        band=HealthBand.UNKNOWN,
        confidence=0.0,
        missing_data=[reason],
        null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
    )


__all__ = ["get_snapshot_repository", "router"]
