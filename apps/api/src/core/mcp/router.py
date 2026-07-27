"""
TS-E2E-SEC-MCP-001: C2Pro MCP API Router.

Expone el MCP Database Server a través de endpoints REST.

Endpoints:
- POST /api/v1/mcp/query-view - Query vista permitida
- POST /api/v1/mcp/call-function - Llamar función permitida
- GET /api/v1/mcp/views - Listar vistas permitidas
- GET /api/v1/mcp/functions - Listar funciones permitidas
- GET /api/v1/mcp/rate-limit-status - Ver estado de rate limit

Security:
- Requiere autenticación JWT
- Extrae tenant_id del token
- Aplica rate limiting
- Loguea todas las operaciones
"""

import json
import time
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

if TYPE_CHECKING:
    FastAPIRequest = Any
else:
    from fastapi import Request as FastAPIRequest
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.mcp.servers.database_server import (
    DatabaseMCPServer,
    FunctionCallRequest,
    QueryResult,
    ViewQueryRequest,
    get_mcp_server,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/mcp",
    tags=["MCP - Model Context Protocol"],
)


# ===========================================
# DEPENDENCIES
# ===========================================


async def get_current_tenant_id(request: FastAPIRequest) -> UUID:
    """
    Extrae tenant_id del request state.

    El TenantIsolationMiddleware ya validó el JWT y lo inyectó en request.state
    """
    if not hasattr(request.state, "tenant_id"):
        logger.error("tenant_id_missing_from_state")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return cast(UUID, request.state.tenant_id)


async def get_current_user_id(request: FastAPIRequest) -> UUID | None:
    """Extrae user_id del request state (opcional)."""
    return getattr(request.state, "user_id", None)


# ===========================================
# REQUEST MODELS FOR /execute ENDPOINT
# ===========================================


class MCPExecuteRequest(BaseModel):
    """
    Generic MCP execution request.

    Used for TS-E2E-SEC-MCP-001 test suite.
    """

    operation: str = Field(..., description="Operation name (view or function)")
    params: dict[str, Any] = Field(default_factory=dict, description="Operation parameters")


# Allowlist for /execute endpoint (from PLAN_ARQUITECTURA_v2.1.md)
EXECUTE_ALLOWED_VIEWS = {
    "projects_summary",
    "alerts_active",
    "coherence_latest",
    "documents_metadata",
    "stakeholders_list",
    "wbs_structure",
    "bom_items",
    "audit_recent",
}

EXECUTE_ALLOWED_FUNCTIONS = {
    "create_alert",
    "update_score",
    "flag_review",
    "add_note",
    "trigger_recalc",
}

# Destructive operations that are NEVER allowed
DESTRUCTIVE_OPERATIONS = {
    "delete_all",
    "drop_table",
    "truncate_table",
    "delete_tenant",
    "modify_schema",
}

EXECUTE_VIEW_TO_DB_VIEW = {
    "projects_summary": "v_project_summary",
    "alerts_active": "v_project_alerts",
    "coherence_latest": "v_coherence_breakdown",
    "documents_metadata": None,
    "stakeholders_list": "v_project_stakeholders",
    "wbs_structure": "v_project_wbs",
    "bom_items": "v_project_bom",
    "audit_recent": None,
}

EXECUTE_FUNCTION_TO_DB_FUNCTION = {
    "create_alert": "fn_create_alert",
    "update_score": "fn_update_score",
    "flag_review": "fn_flag_review",
    "add_note": "fn_add_note",
    "trigger_recalc": "fn_trigger_recalc",
}


def _parse_limit(params: dict[str, Any], default: int = 100) -> int:
    return min(int(params.get("limit", default)), 1000)


def _parse_offset(params: dict[str, Any]) -> int:
    return int(params.get("offset", 0))


def _build_query_result(
    *,
    data: list[dict[str, Any]],
    execution_time_ms: float,
    view_name: str | None = None,
    function_name: str | None = None,
) -> QueryResult:
    return QueryResult(
        data=data,
        row_count=len(data),
        execution_time_ms=round(execution_time_ms, 2),
        view_name=view_name,
        function_name=function_name,
    )


async def _safe_audit_query(
    *,
    mcp_server: DatabaseMCPServer,
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID | None,
    query_type: Literal["view", "function"],
    view_name: str | None,
    function_name: str | None,
    project_id: UUID | None,
    row_count: int,
    execution_time_ms: float,
) -> None:
    try:
        # Isolate the audit write in its own SAVEPOINT: if it fails, only this
        # savepoint is rolled back. Without this, a failed audit INSERT leaves
        # the whole session's transaction aborted, and the caller's later
        # `session.commit()` (see get_session) silently discards the mutation
        # this audit entry was meant to log — even though the API already
        # returned a 200 with the (never-persisted) result.
        async with db.begin_nested():
            await mcp_server._log_query(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                query_type=query_type,
                view_name=view_name,
                function_name=function_name,
                project_id=project_id,
                row_count=row_count,
                execution_time_ms=execution_time_ms,
            )
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning(
            "mcp_audit_log_unavailable",
            error=str(exc),
            tenant_id=str(tenant_id),
            view_name=view_name,
            function_name=function_name,
        )


async def _execute_documents_metadata_query(
    db: AsyncSession,
    tenant_id: UUID,
    params: dict[str, Any],
) -> QueryResult:
    start_time = time.perf_counter()
    query_params = {
        "tenant_id": tenant_id,
        "project_id": params.get("project_id"),
        "limit": _parse_limit(params),
        "offset": _parse_offset(params),
    }
    result = await db.execute(
        text(
            """
            SELECT
                d.id,
                d.project_id,
                p.tenant_id,
                d.filename,
                d.document_type,
                d.file_format,
                d.upload_status,
                d.file_size_bytes,
                d.created_at,
                d.updated_at
            FROM documents AS d
            JOIN projects AS p ON p.id = d.project_id
            WHERE p.tenant_id = :tenant_id
              AND (:project_id IS NULL OR d.project_id = :project_id)
            ORDER BY d.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        query_params,
    )
    data = [dict(row) for row in result.mappings().all()]
    return _build_query_result(
        data=data,
        execution_time_ms=(time.perf_counter() - start_time) * 1000,
        view_name="v_documents_metadata",
    )


async def _execute_audit_recent_query(
    db: AsyncSession,
    tenant_id: UUID,
    params: dict[str, Any],
) -> QueryResult:
    start_time = time.perf_counter()
    query_params = {
        "tenant_id": tenant_id,
        "limit": _parse_limit(params),
        "offset": _parse_offset(params),
    }
    table_exists = await db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'audit_logs'
            )
            """
        )
    )
    if not bool(table_exists.scalar()):
        return _build_query_result(
            data=[],
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            view_name="v_audit_recent",
        )

    result = await db.execute(
        text(
            """
            SELECT
                id,
                tenant_id,
                user_id,
                action,
                resource_type,
                resource_id,
                changes,
                created_at
            FROM audit_logs
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        query_params,
    )
    data = [dict(row) for row in result.mappings().all()]
    return _build_query_result(
        data=data,
        execution_time_ms=(time.perf_counter() - start_time) * 1000,
        view_name="v_audit_recent",
    )


def _require_param(params: dict[str, Any], name: str) -> str:
    value = params.get(name)
    if value in (None, ""):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Parameter '{name}' is required for this operation",
        )
    return str(value)


async def _execute_function_operation(
    operation: str,
    db: AsyncSession,
    tenant_id: UUID,
    params: dict[str, Any],
) -> QueryResult:
    start_time = time.perf_counter()

    if operation == "create_alert":
        query_params = {
            "tenant_id": tenant_id,
            "project_id": UUID(_require_param(params, "project_id")),
            "rule_code": _require_param(params, "rule_code"),
            "severity": _require_param(params, "severity"),
            "title": _require_param(params, "message"),
            "description": _require_param(params, "message"),
            "category": str(params.get("category", "general")),
            "affected_entities": json.dumps(params.get("affected_entities", {})),
        }
        result = await db.execute(
            text(
                """
                INSERT INTO alerts (
                    id,
                    tenant_id,
                    project_id,
                    severity,
                    alert_type,
                    category,
                    rule_id,
                    title,
                    message,
                    description,
                    affected_entities,
                    alert_metadata,
                    status,
                    approval_status,
                    created_at,
                    updated_at
                )
                SELECT
                    gen_random_uuid(),
                    p.tenant_id,
                    p.id,
                    CAST(:severity AS alertseverity),
                    'risk'::alerttype,
                    :category,
                    :rule_code,
                    :title,
                    :description,
                    :description,
                    CAST(:affected_entities AS JSONB),
                    '{}'::jsonb,
                    'open'::alertstatus,
                    'PENDING'::approvalstatus,
                    NOW(),
                    NOW()
                FROM projects AS p
                WHERE p.id = :project_id AND p.tenant_id = :tenant_id
                RETURNING id, project_id, severity::text AS severity, rule_id, title AS message, status::text AS status, approval_status::text AS approval_status, created_at
                """
            ),
            query_params,
        )
    elif operation == "update_score":
        query_params = {
            "tenant_id": tenant_id,
            "project_id": UUID(_require_param(params, "project_id")),
            "score": float(_require_param(params, "score")),
        }
        result = await db.execute(
            text(
                """
                UPDATE projects
                SET coherence_score = :score,
                    last_analysis_at = NOW(),
                    updated_at = NOW()
                WHERE id = :project_id AND tenant_id = :tenant_id
                RETURNING id AS project_id, coherence_score, last_analysis_at
                """
            ),
            query_params,
        )
    elif operation == "flag_review":
        query_params = {
            "tenant_id": tenant_id,
            "alert_id": UUID(_require_param(params, "alert_id")),
            "comment": params.get("comment"),
        }
        result = await db.execute(
            text(
                """
                UPDATE alerts AS a
                SET status = 'acknowledged'::alertstatus,
                    approval_status = 'PENDING'::approvalstatus,
                    review_comment = COALESCE(:comment, a.review_comment),
                    updated_at = NOW()
                FROM projects AS p
                WHERE a.project_id = p.id
                  AND a.id = :alert_id
                  AND p.tenant_id = :tenant_id
                RETURNING a.id AS alert_id, a.status::text AS status, a.approval_status::text AS approval_status, a.review_comment
                """
            ),
            query_params,
        )
    elif operation == "add_note":
        query_params = {
            "tenant_id": tenant_id,
            "alert_id": UUID(_require_param(params, "alert_id")),
            "note": _require_param(params, "note"),
        }
        result = await db.execute(
            text(
                """
                UPDATE alerts AS a
                SET resolution_notes = CASE
                        WHEN a.resolution_notes IS NULL OR a.resolution_notes = '' THEN :note
                        ELSE a.resolution_notes || E'\n' || :note
                    END,
                    updated_at = NOW()
                FROM projects AS p
                WHERE a.project_id = p.id
                  AND a.id = :alert_id
                  AND p.tenant_id = :tenant_id
                RETURNING a.id AS alert_id, a.resolution_notes
                """
            ),
            query_params,
        )
    elif operation == "trigger_recalc":
        query_params = {
            "tenant_id": tenant_id,
            "project_id": UUID(_require_param(params, "project_id")),
        }
        result = await db.execute(
            text(
                """
                UPDATE projects
                SET last_analysis_at = NOW(),
                    updated_at = NOW()
                WHERE id = :project_id AND tenant_id = :tenant_id
                RETURNING id AS project_id, last_analysis_at, true AS triggered
                """
            ),
            query_params,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Operation '{operation}' is allowlisted but has no DB-backed MCP mapping yet",
        )

    data = [dict(row) for row in result.mappings().all()]
    return _build_query_result(
        data=data,
        execution_time_ms=(time.perf_counter() - start_time) * 1000,
        function_name=EXECUTE_FUNCTION_TO_DB_FUNCTION[operation],
    )


# ===========================================
# ENDPOINTS
# ===========================================


@router.post(
    "/query-view",
    response_model=QueryResult,
    summary="Query Vista Permitida",
    description="""
    Ejecuta una query sobre una vista permitida.

    **Seguridad:**
    - Solo vistas en allowlist
    - Rate limiting por tenant
    - Query limits (timeout, row count)
    - Auditoría completa

    **Vistas permitidas:**
    - v_project_summary
    - v_project_alerts
    - v_project_clauses
    - v_project_stakeholders
    - v_project_wbs
    - v_project_bom
    - v_coherence_breakdown
    - v_raci_matrix
    """,
)
async def query_view(
    request: ViewQueryRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID | None = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
    mcp_server: DatabaseMCPServer = Depends(get_mcp_server),
) -> QueryResult:
    """
    Query una vista permitida.

    Example:
        ```json
        {
            "view_name": "v_project_summary",
            "project_id": "123e4567-e89b-12d3-a456-426614174000",
            "filters": {
                "status": "active"
            },
            "limit": 50,
            "offset": 0
        }
        ```
    """
    try:
        result = await mcp_server.query_view(
            request=request,
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        return result

    except ValueError as e:
        logger.warning(
            "mcp_invalid_request",
            error=str(e),
            view_name=request.view_name,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except PermissionError as e:
        logger.warning(
            "mcp_rate_limit_exceeded",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    except Exception as e:
        logger.error(
            "mcp_query_failed",
            error=str(e),
            view_name=request.view_name,
            tenant_id=str(tenant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Query execution failed"
        )


@router.post(
    "/call-function",
    response_model=QueryResult,
    summary="Llamar Función Permitida",
    description="""
    Ejecuta una función permitida.

    **Seguridad:**
    - Solo funciones en allowlist
    - Validación de parámetros
    - Rate limiting
    - Auditoría

    **Funciones permitidas:**
    - fn_get_clause_by_id
    - fn_get_stakeholder_by_id
    - fn_get_neighbors (Knowledge Graph)
    - fn_find_path (Knowledge Graph)
    - fn_get_subgraph (Knowledge Graph)
    """,
)
async def call_function(
    request: FunctionCallRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID | None = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
    mcp_server: DatabaseMCPServer = Depends(get_mcp_server),
) -> QueryResult:
    """
    Llama una función permitida.

    Example:
        ```json
        {
            "function_name": "fn_get_clause_by_id",
            "params": {
                "clause_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
        ```
    """
    try:
        result = await mcp_server.call_function(
            request=request,
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        return result

    except ValueError as e:
        logger.warning(
            "mcp_invalid_function_call",
            error=str(e),
            function_name=request.function_name,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except PermissionError as e:
        logger.warning(
            "mcp_rate_limit_exceeded",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    except Exception as e:
        logger.error(
            "mcp_function_call_failed",
            error=str(e),
            function_name=request.function_name,
            tenant_id=str(tenant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Function call failed"
        )


@router.get(
    "/views",
    response_model=dict[str, list[str]],
    summary="Listar Vistas Permitidas",
    description="Retorna la lista de vistas permitidas en el MCP Server.",
)
async def list_allowed_views() -> dict[str, list[str]]:
    """
    Lista vistas permitidas.

    Returns:
        ```json
        {
            "views": [
                "v_project_summary",
                "v_project_alerts",
                ...
            ]
        }
        ```
    """
    return {"views": DatabaseMCPServer.get_allowed_views()}


@router.get(
    "/functions",
    response_model=dict[str, list[str]],
    summary="Listar Funciones Permitidas",
    description="Retorna la lista de funciones permitidas en el MCP Server.",
)
async def list_allowed_functions() -> dict[str, list[str]]:
    """
    Lista funciones permitidas.

    Returns:
        ```json
        {
            "functions": [
                "fn_get_clause_by_id",
                "fn_get_stakeholder_by_id",
                ...
            ]
        }
        ```
    """
    return {"functions": DatabaseMCPServer.get_allowed_functions()}


@router.get(
    "/rate-limit-status",
    summary="Estado de Rate Limit",
    description="Retorna el estado actual del rate limit para el tenant actual.",
)
async def get_rate_limit_status(
    tenant_id: UUID = Depends(get_current_tenant_id),
    mcp_server: DatabaseMCPServer = Depends(get_mcp_server),
) -> dict[str, Any]:
    """
    Obtiene estado del rate limit.

    Returns:
        ```json
        {
            "requests_in_window": 45,
            "limit": 60,
            "remaining": 15,
            "window_seconds": 60
        }
        ```
    """
    return await mcp_server.get_rate_limit_status(tenant_id)


@router.post(
    "/execute",
    summary="Execute MCP Operation",
    description="""
    Generic MCP operation execution endpoint.

    **For TS-E2E-SEC-MCP-001 E2E tests.**

    Security features:
    - Allowlist validation (views + functions)
    - Blocks destructive operations
    - Rate limiting (60 req/min per tenant)
    - Query limits (5s timeout, 1000 rows)
    - Audit logging
    - Tenant isolation
    """,
)
async def execute_mcp_operation(
    request: MCPExecuteRequest,
    _fastapi_request: FastAPIRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID | None = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
    mcp_server: DatabaseMCPServer = Depends(get_mcp_server),
) -> dict[str, Any]:
    """
    Execute MCP operation (view or function).

    Example:
        ```json
        {
            "operation": "projects_summary",
            "params": {}
        }
        ```

    Returns:
        - 200 OK: Operation succeeded
        - 403 Forbidden: Operation not in allowlist or destructive
        - 429 Too Many Requests: Rate limit exceeded
        - 422 Unprocessable Entity: Invalid request format
    """
    operation = request.operation

    # Check for destructive operations FIRST (security)
    if operation in DESTRUCTIVE_OPERATIONS:
        logger.warning(
            "mcp_destructive_operation_blocked",
            operation=operation,
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation '{operation}' is not allowed (destructive operation)",
        )

    # Check rate limit
    try:
        await mcp_server._check_rate_limit(tenant_id)
    except PermissionError as e:
        logger.warning(
            "mcp_rate_limit_exceeded",
            tenant_id=str(tenant_id),
            operation=operation,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "60"},
        )

    async def _relation_exists(relation_name: str) -> bool:
        result = await db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_views
                    WHERE schemaname = 'public' AND viewname = :relation_name
                )
                """
            ),
            {"relation_name": relation_name},
        )
        return bool(result.scalar())

    async def _function_exists(function_name: str) -> bool:
        result = await db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public' AND p.proname = :function_name
                )
                """
            ),
            {"function_name": function_name},
        )
        return bool(result.scalar())

    # Check if operation is in allowlist (views or functions)
    if operation in EXECUTE_ALLOWED_VIEWS:
        mapped_view = EXECUTE_VIEW_TO_DB_VIEW.get(operation)
        logger.info(
            "mcp_execute_view",
            operation=operation,
            tenant_id=str(tenant_id),
            mapped_view=mapped_view,
        )
        if operation == "documents_metadata":
            result = await _execute_documents_metadata_query(db, tenant_id, request.params)
            await _safe_audit_query(
                mcp_server=mcp_server,
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                query_type="view",
                view_name=result.view_name,
                function_name=None,
                project_id=request.params.get("project_id"),
                row_count=result.row_count,
                execution_time_ms=result.execution_time_ms,
            )
            payload = result.model_dump()
            payload["operation"] = operation
            payload["status"] = "success"
            payload["truncated"] = result.row_count >= _parse_limit(request.params)
            return payload
        if operation == "audit_recent":
            result = await _execute_audit_recent_query(db, tenant_id, request.params)
            await _safe_audit_query(
                mcp_server=mcp_server,
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                query_type="view",
                view_name=result.view_name,
                function_name=None,
                project_id=request.params.get("project_id"),
                row_count=result.row_count,
                execution_time_ms=result.execution_time_ms,
            )
            payload = result.model_dump()
            payload["operation"] = operation
            payload["status"] = "success"
            payload["truncated"] = result.row_count >= _parse_limit(request.params)
            return payload
        if not mapped_view:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Operation '{operation}' is allowlisted but has no DB-backed MCP mapping yet",
            )
        if not await _relation_exists(mapped_view):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Underlying MCP view '{mapped_view}' is not available",
            )

        result = await mcp_server.query_view(
            request=ViewQueryRequest(
                view_name=mapped_view,
                project_id=request.params.get("project_id"),
                filters=request.params.get("filters", {}),
                limit=_parse_limit(request.params),
                offset=_parse_offset(request.params),
            ),
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        payload = result.model_dump()
        payload["operation"] = operation
        payload["status"] = "success"
        payload["truncated"] = result.row_count >= _parse_limit(request.params)
        return payload

    elif operation in EXECUTE_ALLOWED_FUNCTIONS:
        mapped_function = EXECUTE_FUNCTION_TO_DB_FUNCTION.get(operation)
        logger.info(
            "mcp_execute_function",
            operation=operation,
            tenant_id=str(tenant_id),
            mapped_function=mapped_function,
        )
        result = await _execute_function_operation(operation, db, tenant_id, request.params)
        await _safe_audit_query(
            mcp_server=mcp_server,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            query_type="function",
            view_name=None,
            function_name=mapped_function,
            project_id=request.params.get("project_id"),
            row_count=result.row_count,
            execution_time_ms=result.execution_time_ms,
        )
        payload = result.model_dump()
        payload["operation"] = operation
        payload["status"] = "success"
        return payload

    else:
        # Unknown operation - not in allowlist
        logger.warning(
            "mcp_unknown_operation_blocked",
            operation=operation,
            tenant_id=str(tenant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation '{operation}' is not allowed",
        )
