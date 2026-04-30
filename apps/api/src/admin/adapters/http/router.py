"""Test Suite ID: TS-BCK-042-001.

HTTP routes for DLQ admin operations.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from src.admin.application.dtos.dlq import (
    DLQEntryResponse,
    DLQListResponse,
    DLQRetryResponse,
    DLQStatus,
)
from src.admin.application.use_cases.list_dlq_entries import (
    DLQAdminPort,
    DLQEntryView,
    ListDLQEntriesUseCase,
)
from src.admin.application.use_cases.retry_dlq_entry import (
    DLQEntryNotFoundError,
    RetryDLQEntryUseCase,
)
from src.core.database import get_raw_session
from src.core.dlq.dlq_service import DLQService
from src.core.dlq.models import DLQFailedTask
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User, UserRole
from src.core.security import security_scheme


class DLQServiceAdminAdapter:
    """TS-BCK-042-001: Admin adapter around the existing DLQ service."""

    def __init__(self, service: DLQService | None = None) -> None:
        self._service = service or DLQService()

    async def list_by_status(self, status: str) -> list[DLQEntryView]:
        """List DLQ entries across tenants for organization-admin review."""
        async with get_raw_session() as session:
            result = await session.execute(
                select(DLQFailedTask)
                .where(DLQFailedTask.status == status)
                .order_by(DLQFailedTask.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_by_id(self, dlq_id: UUID) -> DLQEntryView | None:
        """Return a DLQ entry by id using the existing service read path."""
        return await self._service.get_by_id(dlq_id)

    async def retry(self, dlq_id: UUID) -> None:
        """Retry a DLQ entry using the existing service retry path."""
        await self._service.increment_retry(dlq_id)


def get_dlq_admin_port() -> DLQAdminPort:
    """TS-BCK-042-001: Provide the DLQ admin port for dependency overrides."""
    return DLQServiceAdminAdapter()


def get_list_dlq_entries_use_case(
    port: DLQAdminPort = Depends(get_dlq_admin_port),
) -> ListDLQEntriesUseCase:
    """TS-BCK-042-001: Provide the list DLQ entries use case."""
    return ListDLQEntriesUseCase(port)


def get_retry_dlq_entry_use_case(
    port: DLQAdminPort = Depends(get_dlq_admin_port),
) -> RetryDLQEntryUseCase:
    """TS-BCK-042-001: Provide the retry DLQ entry use case."""
    return RetryDLQEntryUseCase(port)


async def require_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """TS-BCK-042-001: Reuse existing user role auth for admin-only endpoints."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires admin role",
        )
    return current_user


router = APIRouter(
    prefix="/admin/dlq",
    tags=["Admin", "DLQ"],
    dependencies=[Depends(security_scheme), Depends(require_admin_user)],
)


@router.get(
    "",
    response_model=DLQListResponse,
    summary="List DLQ entries by status",
)
async def list_dlq_entries(
    status_filter: DLQStatus = Query("pending", alias="status"),
    use_case: ListDLQEntriesUseCase = Depends(get_list_dlq_entries_use_case),
) -> DLQListResponse:
    """TS-BCK-042-001: List DLQ entries for organization administrators."""
    entries = await use_case.execute(status=status_filter)
    return DLQListResponse(
        entries=[DLQEntryResponse.model_validate(entry) for entry in entries]
    )


@router.post(
    "/{dlq_id}/retry",
    response_model=DLQRetryResponse,
    summary="Retry a DLQ entry",
)
async def retry_dlq_entry(
    dlq_id: UUID,
    use_case: RetryDLQEntryUseCase = Depends(get_retry_dlq_entry_use_case),
) -> DLQRetryResponse:
    """TS-BCK-042-001: Retry a DLQ entry for organization administrators."""
    try:
        entry = await use_case.execute(dlq_id)
    except DLQEntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DLQ entry not found",
        ) from exc

    return DLQRetryResponse(id=entry.id, status="retrying")
