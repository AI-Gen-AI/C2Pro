"""Admin HTTP routes for Dead Letter Queue operations.

Refers to Suite ID: TS-BCK-042-001.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from src.core.dlq.dlq_service import DLQService
from src.core.middleware.clerk_auth import require_admin
from src.core.security import CurrentTenantId, security_scheme


class DLQTaskResponse(BaseModel):
    """TS-BCK-042-001: Serialized DLQ task for admin list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    task_type: str
    document_id: UUID | None
    payload_json: dict[str, Any]
    error_message: str
    error_traceback: str | None
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    updated_at: datetime
    next_retry_at: datetime | None


class DLQListResponse(BaseModel):
    """TS-BCK-042-001: Admin DLQ list response."""

    tasks: list[DLQTaskResponse]


class DLQRetryResponse(BaseModel):
    """TS-BCK-042-001: Admin DLQ retry response."""

    id: UUID
    status: str


def get_dlq_service() -> DLQService:
    """Provide DLQ service for dependency overrides in tests."""
    return DLQService()


router = APIRouter(
    prefix="/admin/dlq",
    tags=["Admin", "DLQ"],
    dependencies=[Depends(security_scheme), Depends(require_admin)],
)


@router.get(
    "",
    response_model=DLQListResponse,
    summary="List DLQ tasks by status",
)
async def list_dlq_tasks(
    tenant_id: CurrentTenantId,
    status_filter: str = Query("pending", alias="status"),
    service: DLQService = Depends(get_dlq_service),
) -> DLQListResponse:
    """TS-BCK-042-001: List tenant-scoped DLQ tasks for administrators."""
    tasks = await service.get_by_status(tenant_id, status_filter)
    return DLQListResponse(tasks=[DLQTaskResponse.model_validate(task) for task in tasks])


@router.post(
    "/{dlq_id}/retry",
    response_model=DLQRetryResponse,
    summary="Retry a DLQ task",
)
async def retry_dlq_task(
    dlq_id: UUID,
    tenant_id: CurrentTenantId,
    service: DLQService = Depends(get_dlq_service),
) -> DLQRetryResponse:
    """TS-BCK-042-001: Retry a tenant-owned DLQ task."""
    task = await service.get_by_id(dlq_id)
    if task is None or task.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLQ task not found")

    await service.increment_retry(dlq_id)
    return DLQRetryResponse(id=dlq_id, status="retrying")
