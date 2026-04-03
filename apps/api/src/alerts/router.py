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
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import Tenant, User
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
    root_cause: str | None = None


class BulkResolveRequest(BaseModel):
    """Request to bulk resolve alerts."""

    alert_ids: list[str]
    resolution: str
    root_cause: str | None = None


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
    root_cause: str | None = None
    sla_policy_name: str | None = None
    sla_due_at: datetime | None = None
    created_at: datetime


class AlertListResponse(BaseModel):
    """Alert list response."""

    items: list[AlertResponse]
    total: int


class AlertRuleConfigPayload(BaseModel):
    """Tenant-scoped alert rule configuration."""

    id: str
    name: str
    description: str
    enabled: bool
    threshold: int
    severity: Literal["Critical", "High", "Medium"]


class AlertSubscriptionConfigPayload(BaseModel):
    """Tenant-scoped alert subscription configuration."""

    emailEnabled: bool = False
    emailAddress: str = ""
    slackEnabled: bool = False
    slackChannel: str = ""

    @field_validator("emailAddress", "slackChannel", mode="before")
    @classmethod
    def _strip_string_values(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_delivery_targets(self) -> "AlertSubscriptionConfigPayload":
        if self.emailEnabled:
            local_part, separator, domain_part = self.emailAddress.partition("@")
            if not separator or not local_part or "." not in domain_part:
                raise ValueError("emailAddress must be a valid email when email notifications are enabled")

        if self.slackEnabled:
            if not self.slackChannel.startswith("#") or len(self.slackChannel) < 2:
                raise ValueError("slackChannel must start with # when Slack notifications are enabled")

        return self


class AlertWorkspaceSettingsPayload(BaseModel):
    """Workspace alert settings persisted per tenant."""

    rules: list[AlertRuleConfigPayload] = Field(default_factory=list)
    subscriptions: AlertSubscriptionConfigPayload | None = None


def _get_sla_policy(alert: Alert) -> tuple[str | None, datetime | None]:
    policy_by_severity = {
        AlertSeverity.CRITICAL: ("Critical severity: first response in 2 hours", 2),
        AlertSeverity.HIGH: ("High severity: response in 24 hours", 24),
        AlertSeverity.MEDIUM: ("Medium severity: response in 72 hours", 72),
        AlertSeverity.LOW: ("Low severity: response in 120 hours", 120),
    }
    policy = policy_by_severity.get(alert.severity)
    if policy is None or alert.created_at is None:
        return None, None

    policy_name, hours = policy
    return policy_name, alert.created_at + timedelta(hours=hours)


def _normalize_affected_entities(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    return {}


def _normalize_alert_metadata(value: object) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _serialize_alert(alert: Alert, tenant_id: UUID) -> AlertResponse:
    sla_policy_name, sla_due_at = _get_sla_policy(alert)
    affected_entities = _normalize_affected_entities(alert.affected_entities)
    alert_metadata = _normalize_alert_metadata(alert.alert_metadata)
    return AlertResponse(
        id=alert.id,
        project_id=alert.project_id,
        tenant_id=tenant_id,
        rule_code=alert.rule_id or "AI_EXTRACTED",
        category=alert.category or "risk",
        severity=alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        message=alert.title,
        status=alert.status.value if hasattr(alert.status, "value") else str(alert.status),
        affected_entities=affected_entities,
        reviewed_by=alert.reviewed_by,
        reviewed_at=alert.reviewed_at,
        root_cause=alert_metadata.get("root_cause"),
        sla_policy_name=sla_policy_name,
        sla_due_at=sla_due_at,
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


def _set_root_cause(alert: Alert, root_cause: str | None) -> None:
    metadata = dict(alert.alert_metadata or {})
    if root_cause:
        metadata["root_cause"] = root_cause
    else:
        metadata.pop("root_cause", None)
    alert.alert_metadata = metadata


def _requires_root_cause(alert: Alert) -> bool:
    return alert.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH}


def _validate_resolution_input(alert: Alert, resolution: str, root_cause: str | None) -> None:
    min_length_by_severity = {
        AlertSeverity.CRITICAL: 50,
        AlertSeverity.HIGH: 20,
        AlertSeverity.MEDIUM: 10,
    }
    minimum_length = min_length_by_severity.get(alert.severity, 0)
    if len(resolution.strip()) < minimum_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resolution notes must be at least {minimum_length} characters for {alert.severity.value} alerts",
        )

    if _requires_root_cause(alert) and not root_cause:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Root cause is required for high or critical alerts",
        )


def _apply_resolution(alert: Alert, current_user: User, resolution: str, root_cause: str | None) -> None:
    _validate_resolution_input(alert, resolution, root_cause)
    normalized_root_cause = (root_cause or "").strip() or None
    if hasattr(alert, "mark_resolved"):
        alert.mark_resolved(current_user.id, resolution)
    else:
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = current_user.id
        alert.resolution_notes = resolution
    _set_root_cause(alert, normalized_root_cause)


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


async def _get_tenant(session, tenant_id: UUID) -> Tenant | None:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


def _get_workspace_settings_payload(tenant: Tenant) -> AlertWorkspaceSettingsPayload:
    settings = dict(tenant.settings or {})
    workspace_settings = settings.get("alerts_workspace", {})
    return AlertWorkspaceSettingsPayload.model_validate(
        {
            "rules": workspace_settings.get("rules", []),
            "subscriptions": workspace_settings.get("subscriptions"),
        }
    )


# ===========================================
# ENDPOINTS
# ===========================================


@router.get("/alerts/workspace-settings", response_model=AlertWorkspaceSettingsPayload)
async def get_alert_workspace_settings(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertWorkspaceSettingsPayload:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        tenant = await _get_tenant(session, current_user.tenant_id)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        return _get_workspace_settings_payload(tenant)


@router.put("/alerts/workspace-settings", response_model=AlertWorkspaceSettingsPayload)
async def put_alert_workspace_settings(
    payload: AlertWorkspaceSettingsPayload,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertWorkspaceSettingsPayload:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        tenant = await _get_tenant(session, current_user.tenant_id)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        settings = dict(tenant.settings or {})
        settings["alerts_workspace"] = payload.model_dump(mode="json")
        tenant.settings = settings
        await session.commit()
        await session.refresh(tenant)

        return _get_workspace_settings_payload(tenant)


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

        _apply_resolution(alert, current_user, request.resolution, request.root_cause)
        alert.resolved_by = request.resolved_by
        normalized_root_cause = (request.root_cause or "").strip() or None
        history_details = {"resolution": request.resolution}
        if normalized_root_cause is not None:
            history_details["root_cause"] = normalized_root_cause
        _append_history(alert, "resolved", current_user.id, **history_details)
        await session.commit()
        await session.refresh(alert)
        return _serialize_alert(alert, current_user.tenant_id)


@router.post("/alerts/bulk-resolve")
async def bulk_resolve_alerts(
    request: BulkResolveRequest,
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
        normalized_root_cause = (request.root_cause or "").strip() or None
        for alert in alerts:
            _apply_resolution(alert, current_user, request.resolution, normalized_root_cause)
            history_details = {"resolution": request.resolution}
            if normalized_root_cause is not None:
                history_details["root_cause"] = normalized_root_cause
            _append_history(alert, "bulk_resolved", current_user.id, **history_details)
        await session.commit()
        return {
            "processed_count": len(alerts),
            "status": "resolved",
            "alert_ids": [str(alert.id) for alert in alerts],
        }


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
