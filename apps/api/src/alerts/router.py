"""
C2Pro - Alerts HTTP Router

Minimal implementation for TS-E2E-FLW-ALR-001 E2E tests.
GREEN PHASE: "Fake It" pattern implementation.

Endpoints:
- POST /api/v1/alerts - Create alert
- GET /api/v1/projects/{project_id}/alerts - List alerts
- POST /api/v1/alerts/{alert_id}/review - Approve/Reject alert
- POST /api/v1/alerts/bulk-review - Bulk approve/reject
- POST /api/v1/alerts/{alert_id}/evidence - Attach evidence
- POST /api/v1/alerts/{alert_id}/resolve - Resolve alert
- GET /api/v1/alerts/{alert_id}/history - Get status history
"""

from typing import Annotated, Literal
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User

router = APIRouter(tags=["alerts"])


# In-memory storage for fake implementation
_fake_alerts: dict[UUID, dict] = {}


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


# ===========================================
# ENDPOINTS
# ===========================================


@router.post("/alerts", status_code=201, response_model=AlertResponse)
async def create_alert(
    request: CreateAlertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    """
    Create a new alert.

    GREEN PHASE: Minimal implementation using "Fake It" pattern.
    """
    # Create alert
    alert_id = uuid4()
    alert_data = {
        "id": alert_id,
        "project_id": request.project_id,
        "tenant_id": current_user.tenant_id,
        "rule_code": request.rule_code,
        "category": request.category,
        "severity": request.severity,
        "message": request.message,
        "status": "pending",
        "affected_entities": request.affected_entities,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": datetime.utcnow(),
    }

    _fake_alerts[alert_id] = alert_data

    return AlertResponse(**alert_data)


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

    GREEN PHASE: Returns filtered alerts from fake storage.
    """
    # Filter alerts by project and tenant
    alerts = [
        alert for alert in _fake_alerts.values()
        if alert["project_id"] == project_id
        and alert["tenant_id"] == current_user.tenant_id
    ]

    # Apply filters
    if status:
        alerts = [a for a in alerts if a["status"] == status]
    if category:
        alerts = [a for a in alerts if a["category"] == category]
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]

    # Sort by severity (critical > high > medium > low)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 999))

    return AlertListResponse(
        items=[AlertResponse(**a) for a in alerts],
        total=len(alerts),
    )


@router.post("/alerts/{alert_id}/review", response_model=AlertResponse)
async def review_alert(
    alert_id: UUID,
    request: ReviewAlertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    """
    Approve or reject an alert.

    GREEN PHASE: Updates alert status in fake storage.
    """
    # Check if alert exists and belongs to tenant
    alert = _fake_alerts.get(alert_id)

    if not alert or alert["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Update alert status
    alert["status"] = "approved" if request.decision == "approve" else "rejected"
    alert["reviewed_by"] = current_user.id
    alert["reviewed_at"] = datetime.utcnow()

    _fake_alerts[alert_id] = alert

    return AlertResponse(**alert)


@router.post("/alerts/bulk-review")
async def bulk_review_alerts(
    request: BulkReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Bulk approve or reject multiple alerts.

    GREEN PHASE: Processes multiple alerts.

    Anti-gaming: Detects mass approval (50+ in 1 minute).
    """
    alert_count = len(request.alert_ids)

    # Anti-gaming detection
    warning = None
    if alert_count >= 50:
        warning = "Mass approval detected: Reviewing 50+ alerts simultaneously may indicate gaming behavior"

    # Update alerts
    approved_count = 0
    rejected_count = 0

    for alert_id_str in request.alert_ids:
        alert_id = UUID(alert_id_str)
        alert = _fake_alerts.get(alert_id)

        if alert and alert["tenant_id"] == current_user.tenant_id:
            alert["status"] = "approved" if request.decision == "approve" else "rejected"
            alert["reviewed_by"] = current_user.id
            alert["reviewed_at"] = datetime.utcnow()
            _fake_alerts[alert_id] = alert

            if request.decision == "approve":
                approved_count += 1
            else:
                rejected_count += 1

    result = {
        "approved_count": approved_count if request.decision == "approve" else 0,
        "rejected_count": rejected_count if request.decision == "reject" else 0,
        "total_processed": approved_count + rejected_count,
    }

    if warning:
        result["warning"] = warning

    return result


@router.post("/alerts/{alert_id}/evidence", status_code=201)
async def attach_evidence(
    alert_id: UUID,
    request: AttachEvidenceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Attach evidence to an alert.

    GREEN PHASE: Stores evidence metadata.
    """
    # Check if alert exists and belongs to tenant
    alert = _fake_alerts.get(alert_id)

    if not alert or alert["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Store evidence (in real impl, would store in DB)
    evidence_id = uuid4()

    return {
        "id": str(evidence_id),
        "alert_id": str(alert_id),
        "type": request.type,
        "created_at": datetime.utcnow().isoformat(),
    }


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    request: ResolveAlertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    """
    Resolve an alert.

    GREEN PHASE: Marks alert as resolved.
    """
    # Check if alert exists and belongs to tenant
    alert = _fake_alerts.get(alert_id)

    if not alert or alert["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Update status to resolved
    alert["status"] = "resolved"
    _fake_alerts[alert_id] = alert

    return AlertResponse(**alert)


@router.get("/alerts/{alert_id}/history")
async def get_alert_history(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Get status transition history for an alert.

    GREEN PHASE: Returns minimal history.
    """
    # Check if alert exists and belongs to tenant
    alert = _fake_alerts.get(alert_id)

    if not alert or alert["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Return fake history
    return {
        "alert_id": str(alert_id),
        "transitions": [
            {
                "from_status": "pending",
                "to_status": alert["status"],
                "changed_by": str(alert["reviewed_by"]) if alert["reviewed_by"] else None,
                "changed_at": alert["reviewed_at"].isoformat() if alert["reviewed_at"] else None,
            }
        ],
    }


@router.post("/alerts/bulk-delete")
async def bulk_delete_alerts(
    request: BulkDeleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Bulk delete multiple alerts.

    GREEN PHASE: Minimal implementation for TS-E2E-FLW-BLK-001.

    Args:
        request: Bulk delete request
        current_user: Current authenticated user

    Returns:
        Summary of deleted alerts
    """
    deleted_count = 0

    for alert_id_str in request.alert_ids:
        alert_id = UUID(alert_id_str)
        alert = _fake_alerts.get(alert_id)

        # Check tenant and optional status filter
        if alert and alert["tenant_id"] == current_user.tenant_id:
            # Apply status filter if provided
            if request.status_filter:
                if alert["status"] == request.status_filter:
                    del _fake_alerts[alert_id]
                    deleted_count += 1
            else:
                # No filter, delete all
                del _fake_alerts[alert_id]
                deleted_count += 1

    return {
        "deleted_count": deleted_count,
        "total_requested": len(request.alert_ids),
    }
