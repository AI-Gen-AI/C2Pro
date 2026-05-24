"""
HTTP Adapter for Alerts Module.

FastAPI router using hexagonal architecture use cases.
Refers to Suite ID: TS-UC-ALR-LST-001, TS-UC-ALR-REV-001, TS-UC-ALR-RSV-001, TS-BUG-ALRT-IMPORT-001, TS-BCK-050-001.

Phase B: Migrating from legacy router.py to hexagonal architecture.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.application.dtos import (
    AlertHistoryResponse,
    AlertListResponse,
    AlertResponse,
    AlertWorkspaceSettingsPayload,
    BulkOperationResponse,
    BulkResolveRequest,
    BulkReviewRequest,
    CreateAlertRequest,
    ResolveAlertRequest,
    ReviewAlertRequest,
)
from src.alerts.application.mappers import AlertMapper
from src.alerts.application.ports.alert_repository import IAlertRepository
from src.alerts.application.ports.tenant_repository import ITenantRepository
from src.alerts.application.use_cases.bulk_resolve_alerts_use_case import (
    BulkResolveAlertsUseCase,
)
from src.alerts.application.use_cases.bulk_review_alerts_use_case import (
    BulkReviewAlertsUseCase,
)
from src.alerts.application.use_cases.create_alert_use_case import CreateAlertUseCase
from src.alerts.application.use_cases.get_alert_workspace_settings_use_case import (
    GetAlertWorkspaceSettingsUseCase,
)
from src.alerts.application.use_cases.list_alerts_use_case import ListAlertsUseCase
from src.alerts.application.use_cases.resolve_alert_use_case import (
    AlertNotFoundError as ResolveAlertNotFoundError,
)
from src.alerts.application.use_cases.resolve_alert_use_case import (
    ResolveAlertUseCase,
)
from src.alerts.application.use_cases.review_alert_use_case import (
    AlertNotFoundError as ReviewAlertNotFoundError,
)
from src.alerts.application.use_cases.review_alert_use_case import (
    ReviewAlertUseCase,
)
from src.alerts.application.use_cases.update_alert_workspace_settings_use_case import (
    UpdateAlertWorkspaceSettingsUseCase,
)
from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId, security_scheme

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(security_scheme)])
project_alerts_router = APIRouter(
    prefix="/projects",
    tags=["alerts"],
    dependencies=[Depends(security_scheme)],
)


def get_alert_repository(
    session: AsyncSession = Depends(get_session),
) -> IAlertRepository:
    from src.alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
    return SqlAlchemyAlertRepository(session=session)


def get_tenant_repository(
    session: AsyncSession = Depends(get_session),
) -> ITenantRepository:
    from src.alerts.adapters.persistence.tenant_repository import SqlAlchemyTenantRepository
    return SqlAlchemyTenantRepository(session=session)


def get_list_alerts_use_case(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> ListAlertsUseCase:
    return ListAlertsUseCase(repository=repository)


def get_create_alert_use_case(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> CreateAlertUseCase:
    return CreateAlertUseCase(repository=repository)


def get_review_alert_use_case(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> ReviewAlertUseCase:
    return ReviewAlertUseCase(repository=repository)


def get_resolve_alert_use_case(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> ResolveAlertUseCase:
    return ResolveAlertUseCase(repository=repository)


def get_bulk_review_use_case(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> BulkReviewAlertsUseCase:
    return BulkReviewAlertsUseCase(repository=repository)


def get_bulk_resolve_use_case(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> BulkResolveAlertsUseCase:
    return BulkResolveAlertsUseCase(repository=repository)


def get_get_settings_use_case(
    repository: ITenantRepository = Depends(get_tenant_repository),
) -> GetAlertWorkspaceSettingsUseCase:
    return GetAlertWorkspaceSettingsUseCase(repository=repository)


def get_update_settings_use_case(
    repository: ITenantRepository = Depends(get_tenant_repository),
) -> UpdateAlertWorkspaceSettingsUseCase:
    return UpdateAlertWorkspaceSettingsUseCase(repository=repository)


@router.get(
    "/workspace-settings",
    response_model=AlertWorkspaceSettingsPayload,
    summary="Get alert workspace settings",
)
async def get_alert_workspace_settings(
    tenant_id: CurrentTenantId,
    use_case: GetAlertWorkspaceSettingsUseCase = Depends(get_get_settings_use_case),
) -> AlertWorkspaceSettingsPayload:
    try:
        return await use_case.execute(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/workspace-settings",
    response_model=AlertWorkspaceSettingsPayload,
    summary="Save alert workspace settings",
)
async def put_alert_workspace_settings(
    payload: AlertWorkspaceSettingsPayload,
    tenant_id: CurrentTenantId,
    use_case: UpdateAlertWorkspaceSettingsUseCase = Depends(get_update_settings_use_case),
) -> AlertWorkspaceSettingsPayload:
    try:
        return await use_case.execute(tenant_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert",
)
async def create_alert(
    request: CreateAlertRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    create_use_case: CreateAlertUseCase = Depends(get_create_alert_use_case),
) -> AlertResponse:
    alert = await create_use_case.execute(
        project_id=request.project_id,
        tenant_id=tenant_id,
        user_id=user_id,
        rule_code=request.rule_code,
        category=request.category,
        severity=request.severity,
        message=request.message,
        affected_entities=request.affected_entities,
    )
    return AlertMapper.to_response(alert, tenant_id)


@router.get(
    "/projects/{project_id}",
    response_model=AlertListResponse,
    summary="List alerts for a project",
)
async def list_project_alerts(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    list_use_case: ListAlertsUseCase = Depends(get_list_alerts_use_case),
    status_filter: str | None = None,
    category: str | None = None,
    severity: str | None = None,
) -> AlertListResponse:
    return await list_use_case.execute_for_project(
        project_id=project_id,
        tenant_id=tenant_id,
        status=status_filter,
        category=category,
        severity=severity,
    )


@project_alerts_router.get(
    "/{project_id}/alerts",
    response_model=AlertListResponse,
    summary="List alerts for a project",
)
async def list_project_alerts_compatibility(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    list_use_case: ListAlertsUseCase = Depends(get_list_alerts_use_case),
    status_filter: str | None = None,
    category: str | None = None,
    severity: str | None = None,
) -> AlertListResponse:
    return await list_project_alerts(
        project_id=project_id,
        tenant_id=tenant_id,
        list_use_case=list_use_case,
        status_filter=status_filter,
        category=category,
        severity=severity,
    )


@router.get(
    "/tenant",
    response_model=AlertListResponse,
    summary="List alerts for tenant",
)
async def list_tenant_alerts(
    tenant_id: CurrentTenantId,
    list_use_case: ListAlertsUseCase = Depends(get_list_alerts_use_case),
    project_id: UUID | None = None,
    document_id: UUID | None = None,
    status_filter: str | None = None,
    category: str | None = None,
    severity: str | None = None,
) -> AlertListResponse:
    return await list_use_case.execute_for_tenant(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        status=status_filter,
        category=category,
        severity=severity,
    )


@router.post(
    "/{alert_id}/review",
    response_model=AlertResponse,
    summary="Review alert (approve/reject)",
)
async def review_alert(
    alert_id: UUID,
    request: ReviewAlertRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    review_use_case: ReviewAlertUseCase = Depends(get_review_alert_use_case),
) -> AlertResponse:
    try:
        return await review_use_case.execute(
            alert_id=alert_id,
            tenant_id=tenant_id,
            user_id=user_id,
            decision=request.decision,
            comment=request.comment,
        )
    except ReviewAlertNotFoundError:
        raise HTTPException(status_code=404, detail="Alert not found")


@router.post(
    "/bulk-review",
    response_model=BulkOperationResponse,
    summary="Bulk approve/reject alerts",
)
async def bulk_review_alerts(
    request: BulkReviewRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    use_case: BulkReviewAlertsUseCase = Depends(get_bulk_review_use_case),
) -> BulkOperationResponse:
    return await use_case.execute(
        alert_ids=request.alert_ids,
        tenant_id=tenant_id,
        user_id=user_id,
        decision=request.decision,
        comment=request.comment,
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve alert",
)
async def resolve_alert(
    alert_id: UUID,
    request: ResolveAlertRequest,
    tenant_id: CurrentTenantId,
    resolve_use_case: ResolveAlertUseCase = Depends(get_resolve_alert_use_case),
) -> AlertResponse:
    try:
        return await resolve_use_case.execute(
            alert_id=alert_id,
            tenant_id=tenant_id,
            user_id=request.resolved_by,
            resolution=request.resolution,
            root_cause=request.root_cause,
        )
    except ResolveAlertNotFoundError:
        raise HTTPException(status_code=404, detail="Alert not found")


@router.post(
    "/bulk-resolve",
    response_model=BulkOperationResponse,
    summary="Bulk resolve alerts",
)
async def bulk_resolve_alerts(
    request: BulkResolveRequest,
    tenant_id: CurrentTenantId,
    use_case: BulkResolveAlertsUseCase = Depends(get_bulk_resolve_use_case),
) -> BulkOperationResponse:
    return await use_case.execute(
        alert_ids=request.alert_ids,
        tenant_id=tenant_id,
        user_id=tenant_id,  # System-level or tenant-level resolution
        resolution=request.resolution,
        root_cause=request.root_cause,
    )


@router.get(
    "/{alert_id}/history",
    response_model=AlertHistoryResponse,
    summary="Get alert status history",
)
async def get_alert_history(
    alert_id: UUID,
    tenant_id: CurrentTenantId,
    repository: IAlertRepository = Depends(get_alert_repository),
) -> AlertHistoryResponse:
    alert = await repository.get_by_id(alert_id, tenant_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    history = alert.alert_metadata.get("history", []) if alert.alert_metadata else []
    return AlertHistoryResponse(
        alert_id=str(alert_id),
        items=history,
    )


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete alert",
)
async def delete_alert(
    alert_id: UUID,
    tenant_id: CurrentTenantId,
    repository: IAlertRepository = Depends(get_alert_repository),
) -> None:
    deleted = await repository.delete(alert_id, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
    await repository.commit()
