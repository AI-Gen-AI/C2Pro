"""
C2Pro - Alerts HTTP Router

Endpoints:
- POST /api/v1/alerts - Create alert
- GET /api/v1/projects/{project_id}/alerts - List alerts (connected to real DB)
- POST /api/v1/alerts/{alert_id}/review - Approve/Reject alert
- POST /api/v1/alerts/bulk-review - Bulk approve/reject
- POST /api/v1/alerts/{alert_id}/evidence - Attach evidence
- POST /api/v1/alerts/{alert_id}/resolve - Resolve alert
- GET /api/v1/alerts/{alert_id}/history - Get status history
"""

from typing import Annotated, Literal
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.approval import ApprovalStatus
from src.core.database import get_session_with_tenant
from src.documents.adapters.persistence.models import ClauseORM
from src.projects.adapters.persistence.models import ProjectORM

router = APIRouter(tags=["alerts"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class CreateAlertRequest(BaseModel):
    """Request to create an alert."""

    project_id: UUID
    rule_code: str
    category: Literal["SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"]
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    affected_entities: dict = Field(default_factory=dict)


class ReviewAlertRequest(BaseModel):
    """Request to review an alert."""

    decision: Literal["approve", "reject"]
    comment: str = ""


class BulkReviewRequest(BaseModel):
    """Request to bulk review alerts."""

    alert_ids: list[str]
    decision: Literal["approve", "reject"]
    comment: str = ""


class BulkDeleteRequest(BaseModel):
    """Request to bulk delete alerts."""

    alert_ids: list[str]
    status_filter: str | None = None


class AttachEvidenceRequest(BaseModel):
    """Request to attach evidence to alert."""

    type: Literal["note", "screenshot", "document_excerpt"]
    content: str
    source: str = "manual_review"


class ResolveAlertRequest(BaseModel):
    """Request to resolve an alert."""

    resolution: str
    resolved_by: UUID


class AlertResponse(BaseModel):
    """Alert response model."""

    id: UUID
    project_id: UUID
    tenant_id: UUID
    rule_code: str
    category: str
    severity: str
    message: str
    status: str
    affected_entities: dict = Field(default_factory=dict)
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class AlertListResponse(BaseModel):
    """Alert list response."""

    items: list[AlertResponse]
    total: int


def _serialize_alert(alert: Alert, tenant_id: UUID) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        project_id=alert.project_id,
        tenant_id=tenant_id,
        rule_code=alert.rule_id or "AI_EXTRACTED",
        category=alert.category or "risk",
        severity=alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        message=alert.title,
        status=alert.status.value if hasattr(alert.status, "value") else str(alert.status),
        affected_entities=alert.affected_entities or {},
        reviewed_by=alert.reviewed_by,
        reviewed_at=alert.reviewed_at,
        created_at=alert.created_at,
    )


async def _get_project_for_tenant(session, project_id: UUID, tenant_id: UUID) -> ProjectORM | None:
    result = await session.execute(
        select(ProjectORM).where(
            ProjectORM.id == project_id,
            ProjectORM.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_alert_for_tenant(session, alert_id: UUID, tenant_id: UUID) -> Alert | None:
    result = await session.execute(
        select(Alert)
        .join(ProjectORM, ProjectORM.id == Alert.project_id)
        .where(
            Alert.id == alert_id,
            ProjectORM.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


def _metadata_bucket(alert: Alert, key: str) -> list[dict]:
    metadata = dict(alert.alert_metadata or {})
    bucket = list(metadata.get(key, []))
    metadata[key] = bucket
    alert.alert_metadata = metadata
    return bucket


def _append_history(alert: Alert, action: str, user_id: UUID, **details: str) -> None:
    history = _metadata_bucket(alert, "history")
    history.append(
        {
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": str(user_id),
            **details,
        }
    )


def _apply_review(alert: Alert, decision: str, current_user: User, comment: str) -> None:
    alert.reviewed_by = current_user.id
    alert.reviewed_at = datetime.utcnow()
    alert.review_comment = comment
    if decision == "approve":
        alert.approval_status = ApprovalStatus.APPROVED
        alert.status = AlertStatus.ACKNOWLEDGED
    else:
        alert.approval_status = ApprovalStatus.REJECTED
        alert.status = AlertStatus.DISMISSED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = current_user.id
        alert.resolution_notes = comment


def _apply_status_filter(query, raw_status: str):
    normalized = raw_status.lower()
    if normalized == "pending":
        return query.where(Alert.approval_status == ApprovalStatus.PENDING)
    if normalized == "approved":
        return query.where(Alert.approval_status == ApprovalStatus.APPROVED)
    if normalized == "rejected":
        return query.where(Alert.approval_status == ApprovalStatus.REJECTED)
    return query.where(Alert.status == AlertStatus(normalized))


# ===========================================
# ENDPOINTS
# ===========================================


@router.post("/alerts", status_code=201, response_model=AlertResponse)
async def create_alert(
    request: CreateAlertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        project = await _get_project_for_tenant(session, request.project_id, current_user.tenant_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        alert = Alert(
            project_id=request.project_id,
            severity=AlertSeverity(request.severity),
            category=request.category,
            rule_id=request.rule_code,
            title=request.message,
            description=request.message,
            affected_entities=request.affected_entities,
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            alert_metadata={},
        )
        session.add(alert)
        await session.flush()
        _append_history(alert, "created", current_user.id, rule_code=request.rule_code)
        await session.commit()
        await session.refresh(alert)
        return _serialize_alert(alert, current_user.tenant_id)


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    project_id: UUID | None = None,
    document_id: UUID | None = None,
    status: str | None = None,
    category: str | None = None,
    severity: str | None = None,
) -> AlertListResponse:
    """List tenant-scoped alerts with optional project/document filters."""
    async with get_session_with_tenant(current_user.tenant_id) as session:
        query = (
            select(Alert)
            .join(ProjectORM, ProjectORM.id == Alert.project_id)
            .where(ProjectORM.tenant_id == current_user.tenant_id)
        )

        if project_id:
            query = query.where(Alert.project_id == project_id)
        if document_id:
            query = query.join(ClauseORM, ClauseORM.id == Alert.source_clause_id).where(
                ClauseORM.document_id == document_id
            )
        if status:
            query = _apply_status_filter(query, status)
        if category:
            query = query.where(Alert.category == category)
        if severity:
            query = query.where(Alert.severity == AlertSeverity(severity))

        query = query.order_by(Alert.created_at.desc())
        result = await session.execute(query)
        db_alerts = result.scalars().all()

    alerts = [_serialize_alert(alert, current_user.tenant_id) for alert in db_alerts]
    return AlertListResponse(items=alerts, total=len(alerts))


@router.get("/projects/{project_id}/alerts", response_model=AlertListResponse)
async def list_project_alerts(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = None,
    category: str | None = None,
    severity: str | None = None,
) -> AlertListResponse:
    """
    List alerts for a project.

    Returns alerts from the database.
    """
    async with get_session_with_tenant(current_user.tenant_id) as session:
        # Build query
        query = (
            select(Alert)
            .join(ProjectORM, ProjectORM.id == Alert.project_id)
            .where(
                Alert.project_id == project_id,
                ProjectORM.tenant_id == current_user.tenant_id,
            )
        )

        # Apply filters
        if status:
            query = _apply_status_filter(query, status)
        if category:
            query = query.where(Alert.category == category)
        if severity:
            query = query.where(Alert.severity == AlertSeverity(severity))

        # Sort by severity (critical first) then by created_at
        query = query.order_by(Alert.created_at.desc())

        result = await session.execute(query)
        db_alerts = result.scalars().all()

    # Convert to response format
    alerts = [_serialize_alert(alert, current_user.tenant_id) for alert in db_alerts]

    return AlertListResponse(
        items=alerts,
        total=len(alerts),
    )


@router.post("/alerts/{alert_id}/review", response_model=AlertResponse)
async def review_alert(
    alert_id: UUID,
    request: ReviewAlertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        alert = await _get_alert_for_tenant(session, alert_id, current_user.tenant_id)
        if alert is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

        _apply_review(alert, request.decision, current_user, request.comment)
        _append_history(alert, "reviewed", current_user.id, decision=request.decision)
        await session.commit()
        await session.refresh(alert)
        return _serialize_alert(alert, current_user.tenant_id)


@router.post("/alerts/bulk-review")
async def bulk_review_alerts(
    request: BulkReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    alert_ids = [UUID(alert_id) for alert_id in request.alert_ids]
    async with get_session_with_tenant(current_user.tenant_id) as session:
        result = await session.execute(
            select(Alert)
            .join(ProjectORM, ProjectORM.id == Alert.project_id)
            .where(
                Alert.id.in_(alert_ids),
                ProjectORM.tenant_id == current_user.tenant_id,
            )
        )
        alerts = list(result.scalars().all())
        for alert in alerts:
            _apply_review(alert, request.decision, current_user, request.comment)
            _append_history(alert, "bulk_reviewed", current_user.id, decision=request.decision)
        await session.commit()
        warning = None
        if request.decision == "approve" and len(alerts) >= 50:
            warning = "Mass approval pattern detected"
        return {
            "processed_count": len(alerts),
            "decision": request.decision,
            "warning": warning,
        }


@router.post("/alerts/{alert_id}/evidence", status_code=201)
async def attach_evidence(
    alert_id: UUID,
    request: AttachEvidenceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        alert = await _get_alert_for_tenant(session, alert_id, current_user.tenant_id)
        if alert is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

        evidence = _metadata_bucket(alert, "evidence")
        evidence.append(
            {
                "type": request.type,
                "content": request.content,
                "source": request.source,
                "added_by": str(current_user.id),
                "added_at": datetime.utcnow().isoformat(),
            }
        )
        _append_history(alert, "evidence_attached", current_user.id, evidence_type=request.type)
        await session.commit()
        return {
            "alert_id": str(alert.id),
            "evidence_count": len(evidence),
        }


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    request: ResolveAlertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        alert = await _get_alert_for_tenant(session, alert_id, current_user.tenant_id)
        if alert is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

        alert.mark_resolved(current_user.id, request.resolution)
        _append_history(alert, "resolved", current_user.id, resolution=request.resolution)
        await session.commit()
        await session.refresh(alert)
        return _serialize_alert(alert, current_user.tenant_id)


@router.get("/alerts/{alert_id}/history")
async def get_alert_history(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        alert = await _get_alert_for_tenant(session, alert_id, current_user.tenant_id)
        if alert is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        return {
            "alert_id": str(alert.id),
            "items": list((alert.alert_metadata or {}).get("history", [])),
        }


@router.post("/alerts/bulk-delete")
async def bulk_delete_alerts(
    request: BulkDeleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    alert_ids = [UUID(alert_id) for alert_id in request.alert_ids]
    async with get_session_with_tenant(current_user.tenant_id) as session:
        result = await session.execute(
            select(Alert)
            .join(ProjectORM, ProjectORM.id == Alert.project_id)
            .where(
                Alert.id.in_(alert_ids),
                ProjectORM.tenant_id == current_user.tenant_id,
            )
        )
        alerts = list(result.scalars().all())
        deleted_count = 0
        for alert in alerts:
            if request.status_filter == "rejected" and alert.approval_status != ApprovalStatus.REJECTED:
                continue
            await session.delete(alert)
            deleted_count += 1
        await session.commit()
        return {
            "deleted_count": deleted_count,
        }
