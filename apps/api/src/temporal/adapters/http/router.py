"""TS-UT-P0C-TEMPORAL-003 - tenant-scoped temporal change API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.config import settings
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import TenantId, require_tenant_id
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.projects.ports.project_repository import ProjectRepository
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.timeline import (
    InvalidTimelineCursor,
    TimelineScope,
    decode_cursor,
    encode_cursor,
)
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.project_event_repository import IProjectEventRepository

router = APIRouter(prefix="/projects", tags=["Temporal changes"])


class TimelineItemResponse(BaseModel):
    """One immutable event rendered for the What Changed product surface."""

    event_id: UUID
    occurred_at: str
    event_type: str
    state: str
    change_cause: str | None = None
    confidence: float | None = None
    document_id: UUID | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    l3_impact: None = None


class TimelineResponse(BaseModel):
    """Stable cursor page; an empty page means no events, not an unavailable diff."""

    items: list[TimelineItemResponse]
    next_cursor: str | None = None


class ChangeDetailResponse(TimelineItemResponse):
    """Evidence-grounded revision detail with L1/L2 before and after snapshots."""

    changes: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


async def get_event_repository(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[IProjectEventRepository]:
    """Open the event reader with the caller's RLS tenant context."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield SqlAlchemyProjectEventRepository(db)


async def get_project_repository(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[ProjectRepository]:
    """Open the ownership gate with the same RLS tenant context as events."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield SQLAlchemyProjectRepository(db)


def _projection_payload(event: ProjectEvent) -> dict[str, Any]:
    return event.payload if isinstance(event.payload, dict) else {}


def _item(event: ProjectEvent) -> TimelineItemResponse:
    payload = _projection_payload(event)
    document_id = payload.get("document_id")
    return TimelineItemResponse(
        event_id=event.event_id,
        occurred_at=event.occurred_at.isoformat(),
        event_type=event.event_type,
        state=str(payload.get("state") or ("processing" if event.event_type == "revision.ingested" else "ready")),
        change_cause=payload.get("change_cause") if isinstance(payload.get("change_cause"), str) else None,
        confidence=event.confidence,
        document_id=UUID(document_id) if isinstance(document_id, str) else None,
        provenance=cast(dict[str, Any], payload["provenance"]) if isinstance(payload.get("provenance"), dict) else {},
        l3_impact=None,
    )


async def _require_project_access(
    project_id: UUID,
    tenant_id: TenantId,
    projects: ProjectRepository,
) -> None:
    if not await projects.exists_by_id(project_id, tenant_id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/timeline", response_model=TimelineResponse)
async def get_project_timeline(
    project_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    events: IProjectEventRepository = Depends(get_event_repository),
    projects: ProjectRepository = Depends(get_project_repository),
) -> TimelineResponse:
    """Read the append-only project timeline in canonical temporal order."""

    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project_access(project_id, tenant_id, projects)
    scope = TimelineScope(tenant_id=tenant_id, project_id=project_id)
    try:
        after = (
            decode_cursor(cursor, scope=scope, secret=settings.jwt_secret_key)
            if cursor
            else None
        )
    except InvalidTimelineCursor as exc:
        raise HTTPException(status_code=400, detail="Invalid or stale timeline cursor") from exc
    rows = await events.page_for_project(project_id, tenant_id, after=after, limit=limit)
    page_items = rows[:limit]
    next_cursor = (
        encode_cursor(
            page_items[-1].occurred_at,
            page_items[-1].event_id,
            scope=scope,
            secret=settings.jwt_secret_key,
        )
        if len(rows) > limit and page_items
        else None
    )
    return TimelineResponse(items=[_item(event) for event in page_items], next_cursor=next_cursor)


@router.get(
    "/{project_id}/documents/{document_id}/changes/{revision_id}",
    response_model=ChangeDetailResponse,
)
async def get_revision_change_detail(
    project_id: UUID,
    document_id: UUID,
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    events: IProjectEventRepository = Depends(get_event_repository),
    projects: ProjectRepository = Depends(get_project_repository),
) -> ChangeDetailResponse:
    """Read a revision detail only from the tenant-scoped immutable projection."""

    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project_access(project_id, tenant_id, projects)
    event = await events.get_change_for_revision(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Change not found")
    payload = _projection_payload(event)
    provenance = payload.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("target_revision_id") != str(revision_id)
        or payload.get("document_id") != str(document_id)
    ):
        raise HTTPException(status_code=404, detail="Change not found")
    item = _item(event)
    changeset = payload.get("changeset")
    changes = changeset.get("changes", []) if isinstance(changeset, dict) else []
    return ChangeDetailResponse(
        **item.model_dump(),
        changes=changes if isinstance(changes, list) else [],
        evidence_refs=[ref.model_dump(mode="json") for ref in event.evidence_refs],
    )


__all__ = ["get_event_repository", "get_project_repository", "router"]
