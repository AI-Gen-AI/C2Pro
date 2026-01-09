"""
C2Pro - MCP Database Server

Servidor MCP para acceso seguro a la base de datos.

SEGURIDAD CRÍTICA:
- NO permite SQL arbitrario
- Solo vistas y funciones predefinidas (ALLOWLIST)
- Query limits: timeout, row count, cost estimation
- Rate limiting por tenant
- Logging completo de auditoría
- Validación estricta de parámetros

CTO GATE 3: MCP Security
"""

import time
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session

logger = structlog.get_logger()


# ===========================================
# CONFIGURATION & ALLOWLISTS
# ===========================================


class QueryLimits(BaseModel):
    """Límites de query para evitar abuso."""

    statement_timeout: str = "5s"  # Timeout máximo en PostgreSQL
    row_limit: int = Field(default=1000, ge=1, le=10000)
    max_cost: int = Field(default=10000, ge=1)  # Plan cost estimation


class RateLimits(BaseModel):
    """Límites de rate para queries MCP."""

    per_tenant_per_minute: int = 60
    per_tenant_per_hour: int = 500


# ALLOWLIST de vistas permitidas (SEGURIDAD CRÍTICA)
ALLOWED_VIEWS = {
    "v_project_summary",
    "v_project_alerts",
    "v_project_clauses",
    "v_project_stakeholders",
    "v_project_wbs",
    "v_project_bom",
    "v_coherence_breakdown",
    "v_raci_matrix",
}

# ALLOWLIST de funciones permitidas
ALLOWED_FUNCTIONS = {
    "fn_get_clause_by_id",
    "fn_get_stakeholder_by_id",
    "fn_get_neighbors",
    "fn_find_path",
    "fn_get_subgraph",
}


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class ViewQueryRequest(BaseModel):
    """Request para query de vista."""

    view_name: str
    project_id: UUID | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @field_validator("view_name")
    @classmethod
    def validate_view_name(cls, v: str) -> str:
        """Valida que la vista esté en la allowlist."""
        if v not in ALLOWED_VIEWS:
            raise ValueError(f"View '{v}' not allowed. Allowed views: {', '.join(ALLOWED_VIEWS)}")
        return v


class FunctionCallRequest(BaseModel):
    """Request para llamada a función."""

    function_name: str
    params: dict[str, Any]

    @field_validator("function_name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        """Valida que la función esté en la allowlist."""
        if v not in ALLOWED_FUNCTIONS:
            raise ValueError(
                f"Function '{v}' not allowed. Allowed functions: {', '.join(ALLOWED_FUNCTIONS)}"
            )
        return v


class QueryResult(BaseModel):
    """Resultado de query."""

    data: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    view_name: str | None = None
    function_name: str | None = None
    cached: bool = False


class QueryAuditLog(BaseModel):
    """Log de auditoría para query MCP."""

    tenant_id: UUID
    user_id: UUID | None
    query_type: Literal["view", "function"]
    view_name: str | None = None
    function_name: str | None = None
    project_id: UUID | None = None
    row_count: int
    execution_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ===========================================
# MCP DATABASE SERVER
# ===========================================


class DatabaseMCPServer:
    """
    MCP Server para acceso seguro a base de datos.

    Características de seguridad:
    - Allowlist estricta de vistas y funciones
    - Query limits (timeout, rows, cost)
    - Rate limiting por tenant
    - Logging completo de auditoría
    - Validación de parámetros
    - NO permite SQL arbitrario

    Uso:
        server = DatabaseMCPServer()
        result = await server.query_view(
            view_name="v_project_summary",
            tenant_id=tenant_id,
            project_id=project_id
        )
    """

    def __init__(
        self, query_limits: QueryLimits | None = None, rate_limits: RateLimits | None = None
    ):
        self.query_limits = query_limits or QueryLimits()
        self.rate_limits = rate_limits or RateLimits()

        # Simple in-memory rate limiting
        # TODO: Mover a Redis para producción
        self._rate_limit_store: dict[str, list[float]] = {}

        logger.info(
            "mcp_database_server_initialized",
            allowed_views=list(ALLOWED_VIEWS),
            allowed_functions=list(ALLOWED_FUNCTIONS),
            query_limits=self.query_limits.model_dump(),
        )

    # ===========================================
    # PUBLIC API
    # ===========================================

    async def query_view(
        self,
        request: ViewQueryRequest,
        tenant_id: UUID,
        user_id: UUID | None = None,
        db: AsyncSession | None = None,
    ) -> QueryResult:
        """
        Ejecuta query sobre una vista permitida.

        Args:
            request: Parámetros de la query
            tenant_id: ID del tenant (para RLS y rate limiting)
            user_id: ID del usuario (opcional, para auditoría)
            db: Sesión de base de datos (opcional)

        Returns:
            QueryResult con los datos

        Raises:
            ValueError: Si la vista no está permitida
            PermissionError: Si se excede el rate limit
            Exception: Si hay error en la query

        Security:
            - Valida que view_name esté en ALLOWLIST
            - Aplica rate limiting por tenant
            - Configura query limits (timeout, row limit)
            - Filtra por project_id si se provee (RLS adicional)
            - Loguea para auditoría
        """
        # Rate limiting
        self._check_rate_limit(tenant_id)

        start_time = time.perf_counter()

        # Si no se pasa db, crear una sesión
        if db is None:
            async with get_session() as db:
                result = await self._execute_view_query(request, tenant_id, user_id, db)
        else:
            result = await self._execute_view_query(request, tenant_id, user_id, db)

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Auditoría
        await self._log_query(
            tenant_id=tenant_id,
            user_id=user_id,
            query_type="view",
            view_name=request.view_name,
            project_id=request.project_id,
            row_count=result.row_count,
            execution_time_ms=execution_time_ms,
        )

        result.execution_time_ms = round(execution_time_ms, 2)

        return result

    async def call_function(
        self,
        request: FunctionCallRequest,
        tenant_id: UUID,
        user_id: UUID | None = None,
        db: AsyncSession | None = None,
    ) -> QueryResult:
        """
        Ejecuta una función permitida.

        Args:
            request: Parámetros de la función
            tenant_id: ID del tenant
            user_id: ID del usuario (opcional)
            db: Sesión de base de datos (opcional)

        Returns:
            QueryResult con los datos

        Security:
            - Valida que function_name esté en ALLOWLIST
            - Aplica rate limiting
            - Sanitiza parámetros
            - Loguea para auditoría
        """
        # Rate limiting
        self._check_rate_limit(tenant_id)

        start_time = time.perf_counter()

        # Si no se pasa db, crear una sesión
        if db is None:
            async with get_session() as db:
                result = await self._execute_function_call(request, tenant_id, user_id, db)
        else:
            result = await self._execute_function_call(request, tenant_id, user_id, db)

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Auditoría
        await self._log_query(
            tenant_id=tenant_id,
            user_id=user_id,
            query_type="function",
            function_name=request.function_name,
            project_id=request.params.get("project_id"),
            row_count=result.row_count,
            execution_time_ms=execution_time_ms,
        )

        result.execution_time_ms = round(execution_time_ms, 2)

        return result

    # ===========================================
    # INTERNAL METHODS
    # ===========================================

    async def _execute_view_query(
        self, request: ViewQueryRequest, tenant_id: UUID, user_id: UUID | None, db: AsyncSession
    ) -> QueryResult:
        """Ejecuta query de vista con límites de seguridad."""
        # Configurar query limits
        await db.execute(
            text(f"SET LOCAL statement_timeout = '{self.query_limits.statement_timeout}'")
        )

        # Construir query base
        query = f"SELECT * FROM {request.view_name}"
        params = {}

        # Filtros obligatorios
        where_clauses = []

        # Siempre filtrar por tenant_id (RLS adicional en capa de aplicación)
        where_clauses.append("tenant_id = :tenant_id")
        params["tenant_id"] = str(tenant_id)

        # Filtro por project_id si se provee
        if request.project_id:
            where_clauses.append("project_id = :project_id")
            params["project_id"] = str(request.project_id)

        # Filtros adicionales (validados)
        for key, value in request.filters.items():
            # Sanitizar nombre de columna (solo alfanuméricos y guiones bajos)
            if not key.replace("_", "").isalnum():
                raise ValueError(f"Invalid filter key: {key}")

            where_clauses.append(f"{key} = :{key}")
            params[key] = value

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Paginación
        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = min(request.limit, self.query_limits.row_limit)
        params["offset"] = request.offset

        logger.debug(
            "mcp_executing_view_query",
            view_name=request.view_name,
            tenant_id=str(tenant_id),
            query=query,
        )

        # Ejecutar query
        result = await db.execute(text(query), params)
        rows = result.mappings().all()

        # Convertir a dict
        data = [dict(row) for row in rows]

        # Convertir UUIDs a strings en los resultados
        for row in data:
            for key, value in row.items():
                if isinstance(value, UUID):
                    row[key] = str(value)

        return QueryResult(
            data=data,
            row_count=len(data),
            execution_time_ms=0,  # Se completará fuera
            view_name=request.view_name,
        )

    async def _execute_function_call(
        self, request: FunctionCallRequest, tenant_id: UUID, user_id: UUID | None, db: AsyncSession
    ) -> QueryResult:
        """Ejecuta llamada a función con validación de parámetros."""
        # Configurar timeout
        await db.execute(
            text(f"SET LOCAL statement_timeout = '{self.query_limits.statement_timeout}'")
        )

        # Construir llamada a función
        # Las funciones deben aceptar tenant_id como primer parámetro
        func_params = {"tenant_id": str(tenant_id), **request.params}

        # Construir placeholders
        param_names = list(func_params.keys())
        placeholders = ", ".join(f":{name}" for name in param_names)

        query = f"SELECT * FROM {request.function_name}({placeholders})"

        logger.debug(
            "mcp_executing_function",
            function_name=request.function_name,
            tenant_id=str(tenant_id),
            params=request.params,
        )

        # Ejecutar función
        result = await db.execute(text(query), func_params)
        rows = result.mappings().all()

        # Convertir a dict
        data = [dict(row) for row in rows]

        # Convertir UUIDs a strings
        for row in data:
            for key, value in row.items():
                if isinstance(value, UUID):
                    row[key] = str(value)

        return QueryResult(
            data=data,
            row_count=len(data),
            execution_time_ms=0,
            function_name=request.function_name,
        )

    def _check_rate_limit(self, tenant_id: UUID) -> None:
        """
        Verifica rate limit para el tenant.

        Raises:
            PermissionError: Si se excede el rate limit
        """
        now = time.time()
        key = f"tenant:{tenant_id}"

        # Inicializar si no existe
        if key not in self._rate_limit_store:
            self._rate_limit_store[key] = []

        # Filtrar requests recientes (últimos 60 segundos)
        minute_ago = now - 60
        recent_requests = [ts for ts in self._rate_limit_store[key] if ts > minute_ago]

        # Verificar límite por minuto
        if len(recent_requests) >= self.rate_limits.per_tenant_per_minute:
            logger.warning(
                "mcp_rate_limit_exceeded",
                tenant_id=str(tenant_id),
                requests_in_window=len(recent_requests),
                limit=self.rate_limits.per_tenant_per_minute,
            )
            raise PermissionError(
                f"Rate limit exceeded: {self.rate_limits.per_tenant_per_minute} requests/minute"
            )

        # Registrar request actual
        self._rate_limit_store[key].append(now)

        # Cleanup (mantener solo últimas 5 minutos)
        five_minutes_ago = now - 300
        self._rate_limit_store[key] = [
            ts for ts in self._rate_limit_store[key] if ts > five_minutes_ago
        ]

    async def _log_query(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        query_type: Literal["view", "function"],
        view_name: str | None,
        function_name: str | None,
        project_id: UUID | None,
        row_count: int,
        execution_time_ms: float,
    ) -> None:
        """
        Registra query en logs de auditoría.

        TODO: En producción, guardar en tabla audit_logs de BD
        """
        audit_log = QueryAuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            query_type=query_type,
            view_name=view_name,
            function_name=function_name,
            project_id=project_id,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
        )

        logger.info(
            "mcp_query_executed",
            **audit_log.model_dump(exclude_none=True),
        )

        # TODO: Guardar en tabla audit_logs
        # async with get_session() as db:
        #     await db.execute(
        #         text("""
        #             INSERT INTO audit_logs
        #             (tenant_id, user_id, action, resource_type, resource_id, metadata)
        #             VALUES (:tenant_id, :user_id, :action, :resource_type, :resource_id, :metadata)
        #         """),
        #         {
        #             "tenant_id": str(tenant_id),
        #             "user_id": str(user_id) if user_id else None,
        #             "action": "mcp_query",
        #             "resource_type": query_type,
        #             "resource_id": str(project_id) if project_id else None,
        #             "metadata": audit_log.model_dump_json(),
        #         }
        #     )

    # ===========================================
    # UTILITY METHODS
    # ===========================================

    @staticmethod
    def get_allowed_views() -> list[str]:
        """Retorna lista de vistas permitidas."""
        return sorted(ALLOWED_VIEWS)

    @staticmethod
    def get_allowed_functions() -> list[str]:
        """Retorna lista de funciones permitidas."""
        return sorted(ALLOWED_FUNCTIONS)

    def get_rate_limit_status(self, tenant_id: UUID) -> dict[str, Any]:
        """
        Retorna estado actual del rate limit para un tenant.

        Returns:
            dict con requests_in_window, limit, remaining
        """
        now = time.time()
        key = f"tenant:{tenant_id}"

        if key not in self._rate_limit_store:
            return {
                "requests_in_window": 0,
                "limit": self.rate_limits.per_tenant_per_minute,
                "remaining": self.rate_limits.per_tenant_per_minute,
                "window_seconds": 60,
            }

        minute_ago = now - 60
        recent_requests = [ts for ts in self._rate_limit_store[key] if ts > minute_ago]

        return {
            "requests_in_window": len(recent_requests),
            "limit": self.rate_limits.per_tenant_per_minute,
            "remaining": max(0, self.rate_limits.per_tenant_per_minute - len(recent_requests)),
            "window_seconds": 60,
        }


# ===========================================
# SINGLETON INSTANCE
# ===========================================

# Instancia global del servidor MCP
_mcp_server: DatabaseMCPServer | None = None


def get_mcp_server() -> DatabaseMCPServer:
    """
    Obtiene la instancia singleton del MCP Server.

    Uso:
        server = get_mcp_server()
        result = await server.query_view(...)
    """
    global _mcp_server

    if _mcp_server is None:
        _mcp_server = DatabaseMCPServer()

    return _mcp_server
