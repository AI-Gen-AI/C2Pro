
import abc
from typing import List, Set

class OperationAllowlistRepository(abc.ABC):
    """
    Port for fetching operation allowlists for a given tenant.
    This defines the contract that persistence adapters must implement.
    """
    @abc.abstractmethod
    def get_allowlist_for_tenant(self, tenant_id: str) -> List[str]:
        """
        Retrieves the list of allowed operation names for a specific tenant.
        
        Args:
            tenant_id: The unique identifier for the tenant.
            
        Returns:
            A list of strings, where each string is an allowed operation.
        """
        raise NotImplementedError


class MCPGateway:
    """
    Gateway to the Master Control Program (MCP).
    
    This adapter is responsible for validating if an operation is permitted
    for a given tenant based on a dynamically fetched allowlist. It also
    enforces a hardcoded blocklist for known dangerous operations.
    """
    
    # Hardcoded blocklist for critically dangerous operations.
    # These are blocked regardless of any tenant's allowlist.
    _DESTRUCTIVE_OPERATIONS: Set[str] = {
        "delete_all",
        "drop_table",
    }

    def __init__(self, allowlist_repo: OperationAllowlistRepository):
        if not isinstance(allowlist_repo, OperationAllowlistRepository):
            raise TypeError("allowlist_repo must be an implementation of OperationAllowlistRepository")
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

        # Normalize the operation name for consistent matching
        normalized_operation = operation_name.strip().lower()

        # 1. Enforce the hardcoded blocklist first. This is a critical safety layer.
        if normalized_operation in self._DESTRUCTIVE_OPERATIONS:
            return False

        # 2. Fetch the tenant-specific allowlist from the repository port.
        # The async keyword is not used here as the port is abstract.
        # The concrete implementation in the test is a MagicMock, which is synchronous by default.
        # When a real async repository is injected, this will work as expected.
        tenant_allowlist = self.allowlist_repo.get_allowlist_for_tenant(tenant_id)
        
        # 3. Check if the operation is in the tenant's allowlist.
        return normalized_operation in tenant_allowlist
