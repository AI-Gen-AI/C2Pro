"""
C2Pro - Bulk Operations Router

Minimal implementation for TS-E2E-FLW-BLK-001 E2E tests.
GREEN PHASE: "Fake It" pattern implementation.

Endpoints:
- GET /api/v1/bulk-operations/{job_id}/progress - Track operation progress
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.bulk_operations.store import get_job
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.tenants.types import require_tenant_id

router = APIRouter(prefix="/bulk-operations", tags=["bulk-operations"])


@router.get("/{job_id}/progress")
async def get_bulk_operation_progress(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Get progress of a bulk operation.

    GREEN PHASE: Minimal implementation using "Fake It" pattern.

    Args:
        job_id: UUID of the bulk operation job
        current_user: Authenticated user

    Returns:
        Progress information (percentage, status, estimated time)

    Raises:
        404: Job not found
    """
    job = get_job(job_id, tenant_id=require_tenant_id(current_user.tenant_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return {
        "job_id": job_id,
        "status": job.get("status", "processing"),
        "percentage": job.get("percentage", 0),
        "processed_items": job.get("processed_items", 0),
        "total_items": job.get("total_items", 0),
        "eta_seconds": job.get("eta_seconds", 0),
        "started_at": job.get("started_at"),
        "updated_at": job.get("updated_at"),
    }
