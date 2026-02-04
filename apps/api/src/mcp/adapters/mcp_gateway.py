"""
TS-UC-SEC-MCP-001: MCP Gateway allowlist adapter.
"""

from __future__ import annotations

from typing import Protocol


class OperationAllowlistRepository(Protocol):
    """
    Port for fetching operation allowlists for a given tenant.
    Refers to Suite ID: TS-UC-SEC-MCP-001.
    """

    def get_allowlist_for_tenant(self, tenant_id: str) -> list[str]:
        """
        Retrieves the list of allowed operation names for a specific tenant.
        """


class MCPGateway:
    """
    Gateway to the Master Control Program (MCP).
    Refers to Suite ID: TS-UC-SEC-MCP-001.
    """

    _DESTRUCTIVE_OPERATIONS: set[str] = {
        "delete_all",
        "drop_table",
    }

    def __init__(self, allowlist_repo: OperationAllowlistRepository):
        self.allowlist_repo = allowlist_repo

    async def is_operation_allowed(self, tenant_id: str | None, operation_name: str | None) -> bool:
        """
        Validates if a tenant is allowed to perform a given operation.

        Args:
            tenant_id: The ID of the tenant making the request.
            operation_name: The name of the operation to validate.

        Returns:
            True if the operation is allowed, False otherwise.
            
        Raises:
            ValueError: If tenant_id or operation_name are None or empty.
        """
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty or None")
        if not operation_name:
            raise ValueError("Operation name cannot be empty or None")

        normalized_operation = operation_name.strip().lower()

        if normalized_operation in self._DESTRUCTIVE_OPERATIONS:
            return False

        tenant_allowlist = self.allowlist_repo.get_allowlist_for_tenant(tenant_id)
        normalized_allowlist = {operation.strip().lower() for operation in tenant_allowlist}
        return normalized_operation in normalized_allowlist
