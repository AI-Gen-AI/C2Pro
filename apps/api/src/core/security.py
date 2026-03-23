"""
C2Pro - Security

Utilidades de seguridad: validación de JWT, obtención de usuario actual, etc.
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings
from src.core.exceptions import AuthenticationError, TenantNotFoundError

logger = structlog.get_logger()

# HTTP Bearer scheme para OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)


async def get_current_tenant_id(request: Request) -> UUID:
    """
    Obtiene el tenant_id del contexto de la request.

    El TenantIsolationMiddleware debe haber inyectado esto.

    Uso:
        @router.get("/projects")
        async def list_projects(tenant_id: UUID = Depends(get_current_tenant_id)):
            ...
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id is None:
        raise TenantNotFoundError()

    return tenant_id


async def get_current_user_id(request: Request) -> UUID:
    """
    Obtiene el user_id del contexto de la request.

    Uso:
        @router.get("/me")
        async def get_me(user_id: UUID = Depends(get_current_user_id)):
            ...
    """
    user_id = getattr(request.state, "user_id", None)

    if user_id is None:
        raise AuthenticationError("Not authenticated")

    return user_id


async def get_current_user_id_with_bearer(
    request: Request,
    _credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UUID:
    """Same as get_current_user_id, but exposes HTTP Bearer in OpenAPI/Swagger."""
    return await get_current_user_id(request)


async def get_optional_user_id(request: Request) -> UUID | None:
    """
    Obtiene el user_id si existe, None si no está autenticado.

    Útil para endpoints que funcionan con o sin auth.
    """
    return getattr(request.state, "user_id", None)


# Type aliases para Depends más limpios
CurrentTenantId = Annotated[UUID, Depends(get_current_tenant_id)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id_with_bearer)]
OptionalUserId = Annotated[UUID | None, Depends(get_optional_user_id)]


# ===========================================
# PERMISSION CHECKS
# ===========================================


class Permissions:
    """
    Utilidades para verificar permisos.

    Por ahora, simple (tenant-based).
    En el futuro, puede expandirse a RBAC.
    """

    @staticmethod
    async def verify_project_access(project_tenant_id: UUID, current_tenant_id: UUID) -> None:
        """
        Verifica que el usuario tiene acceso al proyecto.

        Raises:
            HTTPException 404 si no tiene acceso (no revelamos que existe)
        """
        if project_tenant_id != current_tenant_id:
            logger.warning(
                "unauthorized_project_access_attempt",
                project_tenant_id=str(project_tenant_id),
                current_tenant_id=str(current_tenant_id),
            )
            # Return 404 instead of 403 to not reveal existence
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


# ===========================================
# API KEY AUTH (para integraciones futuras)
# ===========================================


async def validate_api_key(
    request: Request,
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
