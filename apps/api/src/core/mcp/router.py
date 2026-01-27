"""
C2Pro - MCP API Router

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

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request as FastAPIRequest
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

    return request.state.tenant_id


async def get_current_user_id(request: FastAPIRequest) -> UUID | None:
    """Extrae user_id del request state (opcional)."""
    return getattr(request.state, "user_id", None)


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
) -> dict:
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
    return mcp_server.get_rate_limit_status(tenant_id)
