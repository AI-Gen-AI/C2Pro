"""
C2Pro - Security

Refers to Suite ID: TS-UC-SEC-TNT-001.

Utilidades de seguridad: validacion de JWT, obtencion de usuario actual, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, cast
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings
from src.core.exceptions import AuthenticationError, TenantNotFoundError
from src.core.security.tenant_context import (
    TenantContext,
    TenantIsolationError,
    TenantScopedCache,
)
from src.core.tenants.types import TenantId

logger = structlog.get_logger()

if TYPE_CHECKING:
    RequestType: TypeAlias = Request[Any]
else:
    RequestType = Request

# HTTP Bearer scheme para OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)


async def get_current_tenant_id(request: RequestType) -> UUID:
    """
    Obtiene el tenant_id del contexto de la request.

    El TenantIsolationMiddleware debe haber inyectado esto.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id is None:
        raise cast(type[Exception], TenantNotFoundError)()

    return cast(UUID, tenant_id)


async def get_current_user_id(request: RequestType) -> UUID:
    """
    Obtiene el user_id del contexto de la request.
    """
    user_id = getattr(request.state, "user_id", None)

    if user_id is None:
        raise AuthenticationError("User not authenticated")

    return cast(UUID, user_id)


async def get_current_user_id_with_bearer(
    request: RequestType,
    _credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UUID:
    """Same as get_current_user_id, but exposes HTTP Bearer in OpenAPI/Swagger."""
    return await get_current_user_id(request)


async def get_optional_user_id(request: RequestType) -> UUID | None:
    """
    Obtiene el user_id si existe, None si no esta autenticado.
    """
    return getattr(request.state, "user_id", None)


# Type aliases para Depends mas limpios
CurrentTenantId = Annotated[TenantId, Depends(get_current_tenant_id)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id_with_bearer)]
OptionalUserId = Annotated[UUID | None, Depends(get_optional_user_id)]


class Permissions:
    """
    Utilidades para verificar permisos.
    """

    @staticmethod
    async def verify_project_access(project_tenant_id: UUID, current_tenant_id: UUID) -> None:
        """
        Verifica que el usuario tiene acceso al proyecto.
        """
        if project_tenant_id != current_tenant_id:
            logger.warning(
                "unauthorized_project_access_attempt",
                project_tenant_id=str(project_tenant_id),
                current_tenant_id=str(current_tenant_id),
            )
            # 404 para no revelar existencia de recursos en otros tenants.
            raise HTTPException(status_code=404, detail="Project not found")

    @staticmethod
    async def verify_document_access(document_tenant_id: UUID, current_tenant_id: UUID) -> None:
        """Verifica acceso a documento."""
        if document_tenant_id != current_tenant_id:
            logger.warning(
                "unauthorized_document_access_attempt",
                document_tenant_id=str(document_tenant_id),
                current_tenant_id=str(current_tenant_id),
            )
            raise HTTPException(status_code=404, detail="Document not found")


async def validate_api_key(
    request: RequestType,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> str | None:
    """
    Valida API key para integraciones.

    Retorna el tenant_id asociado al API key, o None si no hay key.
    """
    api_key = request.headers.get("x-api-key")

    if api_key is None and credentials is not None and credentials.scheme.lower() == "apikey":
        api_key = credentials.credentials

    if api_key is None:
        return None

    tenant_id = settings.integration_api_keys.get(api_key)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return tenant_id


__all__ = [
    "CurrentTenantId",
    "CurrentUserId",
    "OptionalUserId",
    "Permissions",
    "TenantContext",
    "TenantIsolationError",
    "TenantScopedCache",
    "get_current_tenant_id",
    "get_current_user_id",
    "get_current_user_id_with_bearer",
    "get_optional_user_id",
    "validate_api_key",
]
