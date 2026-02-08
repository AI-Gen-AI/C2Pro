"""
Validate MCP operation use case.

Refers to Suite ID: TS-UA-SEC-UC-001.
"""

from __future__ import annotations

from src.core.mcp.servers.database_server import DatabaseMCPServer


class ValidateMCPOperationUseCase:
    """Refers to Suite ID: TS-UA-SEC-UC-001."""

    def validate(self, *, operation_type: str, operation_name: str) -> bool:
        if operation_type == "view":
            return operation_name in DatabaseMCPServer.get_allowed_views()
        if operation_type == "function":
            return operation_name in DatabaseMCPServer.get_allowed_functions()
        raise ValueError(f"Unsupported operation type: {operation_type}")
