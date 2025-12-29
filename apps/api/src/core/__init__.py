"""
C2Pro Core Module

Funcionalidades compartidas: database, security, middleware, etc.
"""

from src.core.database import (
    Base,
    get_session,
    get_session_with_tenant,
    TenantSession,
    init_db,
    close_db,
)
from src.core.security import (
    get_current_tenant_id,
    get_current_user_id,
    CurrentTenantId,
    CurrentUserId,
    Permissions,
)
from src.core.exceptions import (
    C2ProException,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
    AIServiceError,
    AIBudgetExceededError,
)

__all__ = [
    # Database
    "Base",
    "get_session",
    "get_session_with_tenant",
    "TenantSession",
    "init_db",
    "close_db",
    # Security
    "get_current_tenant_id",
    "get_current_user_id",
    "CurrentTenantId",
    "CurrentUserId",
    "Permissions",
    # Exceptions
    "C2ProException",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceNotFoundError",
    "ValidationError",
    "AIServiceError",
    "AIBudgetExceededError",
]