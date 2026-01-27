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
from src.core.auth import (
    AuthService,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    SubscriptionPlan,
    Tenant,
    TokenResponse,
    User,
    UserRole,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.core.observability import (
    configure_logging,
    get_version,
    init_sentry,
    record_ai_metric,
    record_cache_hit,
    record_cache_miss,
    record_request_metric,
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
    # Auth
    "User",
    "Tenant",
    "UserRole",
    "SubscriptionPlan",
    "AuthService",
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
    "TokenResponse",
    "create_access_token",
    "decode_token",
    "hash_password",
    "verify_password",
    # Observability
    "configure_logging",
    "init_sentry",
    "get_version",
    "record_request_metric",
    "record_ai_metric",
    "record_cache_hit",
    "record_cache_miss",
]
