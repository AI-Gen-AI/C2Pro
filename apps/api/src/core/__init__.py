"""
C2Pro Core Module

Funcionalidades compartidas: database, security, middleware, MCP, etc.
"""

from src.core.database import (
    Base,
    close_db,
    get_session,
    get_session_with_tenant,
    init_db,
)
from src.core.exceptions import (
    AIBudgetExceededError,
    AIServiceError,
    AuthenticationError,
    AuthorizationError,
    C2ProException,
    ResourceNotFoundError,
    ValidationError,
)
from src.core.mcp.servers.database_server import DatabaseMCPServer, get_mcp_server
from src.core.security import (
    CurrentTenantId,
    CurrentUserId,
    Permissions,
    get_current_tenant_id,
    get_current_user_id,
)

__all__ = [
    # Database
    "Base",
    "get_session",
    "get_session_with_tenant",
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
    # MCP
    "DatabaseMCPServer",
    "get_mcp_server",
]
