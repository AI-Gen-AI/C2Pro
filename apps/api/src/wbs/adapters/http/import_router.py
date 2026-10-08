"""WBS import: parse a WBS source revision, read it, create a DRAFT from it, compare (PC-2b.3 #922).

Minimal surface. The file itself is uploaded through the existing document upload endpoint as a
``wbs`` document (no second blob store). There is NO AI review, generate, auto-apply or
schedule-as-WBS endpoint. The actor is ALWAYS the authenticated session user (request bodies
forbid unknown fields); only a human ``user`` or ``admin`` imports or creates a candidate -- never
``api``, AI or a service. A parsed import never creates a DRAFT; ``POST .../candidates`` is the
explicit human action that does, and the baseline still needs submit + human admin approval.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.wbs.adapters.http.governed_change_router import _actor
from src.wbs.adapters.persistence.import_models import WBSImportSourceORM
from src.wbs.imports.service import WBSImportService

router = APIRouter(prefix="/projects", tags=["WBS import"])

_PREFIX = "/{project_id}/wbs-imports"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------- requests
class CreateWBSImportRequest(_Strict):
    document_id: UUID = Field(description="an existing document of type 'wbs'")
    revision_id: UUID | None = Field(default=None, description="the immutable revision to parse (default: current)")
    parse_config: dict[str, Any] = Field(
        default_factory=dict,
        description="xlsx: {sheet}; csv: {delimiter}; json: {} -- unknown keys are rejected",
    )


class CreateWBSImportCandidateRequest(_Strict):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None


# ---------------------------------------------------------------------------- responses
class WBSImportDiagnostic(BaseModel):
    severity: str = Field(description="WARNING | BLOCKING_ERROR")
    code: str
    message: str
    source_ref: str | None = None
    field: str | None = None


class WBSImportResponse(BaseModel):
    id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    blob_hash: str
    format: str
    parser_id: str
    parser_version: str
    parse_config: dict[str, Any]
    parse_config_digest: str
    import_key: str
    snapshot_schema_version: str
    snapshot_digest: str
    snapshot: dict[str, Any]
    status: str = Field(description="READY | READY_WITH_WARNINGS | INVALID (the parse only; no authority)")
    row_count: int
    warning_count: int
    blocking_count: int
    diagnostics: list[WBSImportDiagnostic]
    created_by: UUID
    created_at: datetime
    reused: bool = False


class WBSImportCandidateResponse(BaseModel):
    change_set_id: UUID
    source_import_id: UUID
    entry_mode: str
    origin: str
    status: str
    revision: int
    node_count: int


class WBSImportProposed(BaseModel):
    status: str = Field(description="NOT_AVAILABLE | DERIVED (a preview simulation, never stored)")
    reason: str | None = None
    reasons: list[str] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class WBSImportComparisonRow(BaseModel):
    source_ref: str
    status: str = Field(description="UNCHANGED | CHANGED | REMOVED | NOT_COMPARABLE (see limitations)")
    node_id: UUID | None = None
    changes: list[str] = Field(default_factory=list, description="Subset of compared_fields that differ")
    limitations: list[str] = Field(default_factory=list,
                                   description="Why the row could not be compared reliably (never UNCHANGED)")
    imported_sibling_position: int | None = Field(None, description="1-based, among the imported siblings")
    candidate_sibling_position: int | None = Field(None, description="1-based, under the candidate parent")


class WBSImportComparisonResponse(BaseModel):
    import_id: UUID
    change_set_id: UUID
    change_set_revision: int
    snapshot_digest: str
    compared_fields: list[str] = Field(default_factory=list)
    imported: list[dict[str, Any]]
    candidate: list[dict[str, Any]]
    proposed: WBSImportProposed
    rows: list[WBSImportComparisonRow]
    added_node_ids: list[UUID]
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------- plumbing
async def get_wbs_import_service(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[WBSImportService]:
    """One tenant-scoped transaction per request (committed on success, rolled back on error)."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield WBSImportService(db)


def _import(source: WBSImportSourceORM, *, reused: bool = False) -> WBSImportResponse:
    return WBSImportResponse(
        id=source.id, project_id=source.project_id, document_id=source.document_id, revision_id=source.revision_id,
        blob_hash=source.blob_hash, format=source.format, parser_id=source.parser_id,
        parser_version=source.parser_version, parse_config=dict(source.parse_config),
        parse_config_digest=source.parse_config_digest, import_key=source.import_key,
        snapshot_schema_version=source.snapshot_schema_version, snapshot_digest=source.snapshot_digest,
        snapshot=dict(source.snapshot), status=source.status, row_count=source.row_count,
        warning_count=source.warning_count, blocking_count=source.blocking_count,
        diagnostics=[WBSImportDiagnostic(**d) for d in source.diagnostics], created_by=source.created_by,
        created_at=source.created_at, reused=reused,
    )


# ---------------------------------------------------------------------------- endpoints
@router.post(_PREFIX, response_model=WBSImportResponse, status_code=status.HTTP_201_CREATED)
async def create_wbs_import(
    project_id: UUID,
    body: CreateWBSImportRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: WBSImportService = Depends(get_wbs_import_service),
) -> WBSImportResponse:
    """Deterministically parse one revision of a ``wbs`` document (200 when the identical import exists)."""
    result = await service.create_import(
        project_id=project_id, tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user),
        document_id=body.document_id, revision_id=body.revision_id, parse_config=body.parse_config,
    )
    if result.reused:
        response.status_code = status.HTTP_200_OK
    return _import(result.source, reused=result.reused)


@router.get(f"{_PREFIX}/{{import_id}}", response_model=WBSImportResponse)
async def get_wbs_import(
    project_id: UUID,
    import_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSImportService = Depends(get_wbs_import_service),
) -> WBSImportResponse:
    source = await service.get_import(project_id=project_id, tenant_id=require_tenant_id(current_user.tenant_id),
                                      import_id=import_id)
    return _import(source)


@router.post(f"{_PREFIX}/{{import_id}}/candidates", response_model=WBSImportCandidateResponse,
             status_code=status.HTTP_201_CREATED)
async def create_wbs_import_candidate(
    project_id: UUID,
    import_id: UUID,
    body: CreateWBSImportCandidateRequest,
    current_user: User = Depends(get_current_user),
    service: WBSImportService = Depends(get_wbs_import_service),
) -> WBSImportCandidateResponse:
    """Explicit human action: a NEW IMPORT_REVIEW DRAFT populated from the import (first baseline only)."""
    result = await service.create_candidate(
        project_id=project_id, tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user),
        import_id=import_id, title=body.title, description=body.description,
    )
    change_set = result.change_set
    return WBSImportCandidateResponse(
        change_set_id=change_set.id, source_import_id=import_id, entry_mode=change_set.entry_mode,
        origin=change_set.origin, status=change_set.status, revision=result.revision,
        node_count=len(result.node_ids_by_source_ref),
    )


@router.get(f"{_PREFIX}/{{import_id}}/comparison", response_model=WBSImportComparisonResponse)
async def compare_wbs_import(
    project_id: UUID,
    import_id: UUID,
    change_set_id: UUID = Query(description="the IMPORT_REVIEW change set created from this import"),
    intelligence_run_id: UUID | None = Query(default=None, description="derive PROPOSED from this run's proposals"),
    current_user: User = Depends(get_current_user),
    service: WBSImportService = Depends(get_wbs_import_service),
) -> WBSImportComparisonResponse:
    """IMPORTED vs CANDIDATE (vs a derived PROPOSED preview): a pure read, zero writes."""
    view = await service.comparison(
        project_id=project_id, tenant_id=require_tenant_id(current_user.tenant_id), import_id=import_id,
        change_set_id=change_set_id, intelligence_run_id=intelligence_run_id,
    )
    return WBSImportComparisonResponse(**view)
