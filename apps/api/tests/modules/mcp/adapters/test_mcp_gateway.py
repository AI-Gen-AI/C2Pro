"""
TS-UC-SEC-MCP-001: MCP Gateway Allowlist Validation tests.
"""

from unittest.mock import MagicMock

import pytest

from src.mcp.adapters.mcp_gateway import MCPGateway, OperationAllowlistRepository

# A fixture to create a gateway with a mocked repository for each test
@pytest.fixture
def mock_repo():
    """Refers to Suite ID: TS-UC-SEC-MCP-001."""
    return MagicMock(spec=OperationAllowlistRepository)

@pytest.fixture
def mcp_gateway(mock_repo):
    """Refers to Suite ID: TS-UC-SEC-MCP-001."""
    return MCPGateway(allowlist_repo=mock_repo)

@pytest.mark.asyncio
class TestMCPGatewayAllowlistValidation:
    """Refers to Suite ID: TS-UC-SEC-MCP-001"""

    # Default tenant for most tests
    DEFAULT_TENANT_ID = "default_tenant"

    # Standard operations that should be allowed by default
    ALLOWED_OPERATIONS = [
        "view_projects_summary",
        "view_alerts_active",
        "view_coherence_latest",
        "view_documents_metadata",
        "view_stakeholders_list",
        "view_wbs_structure",
        "view_bom_items",
        "view_audit_recent",
        "create_alert",
        "update_score",
        "flag_review",
        "add_note",
        "trigger_recalc",
    ]

    # Destructive operations that should always be blocked
    DESTRUCTIVE_OPERATIONS = [
        "delete_all",
        "drop_table",
    ]

    @pytest.mark.parametrize("operation", ALLOWED_OPERATIONS)
    async def test_standard_operations_are_allowed(self, mcp_gateway, mock_repo, operation):
        """
        Tests that standard view and function operations are allowed.
        Covers: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013
        """
        # Setup mock: The default tenant has the standard allowlist
        mock_repo.get_allowlist_for_tenant.return_value = self.ALLOWED_OPERATIONS
        
        result = await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, operation)
        
        assert result is True
        mock_repo.get_allowlist_for_tenant.assert_called_once_with(self.DEFAULT_TENANT_ID)

    async def test_014_unknown_operation_blocked(self, mcp_gateway, mock_repo):
        """Tests that an operation not in the allowlist is blocked."""
        mock_repo.get_allowlist_for_tenant.return_value = self.ALLOWED_OPERATIONS
        
        result = await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, "unknown_operation_xyz")
        
        assert result is False

    @pytest.mark.parametrize("operation", DESTRUCTIVE_OPERATIONS)
    async def test_015_016_destructive_operations_blocked(self, mcp_gateway, mock_repo, operation):
        """Tests that explicitly destructive operations are always blocked, even if in list."""
        # Even if a repo mistakenly allows it, the gateway should enforce this.
        malicious_allowlist = self.ALLOWED_OPERATIONS + self.DESTRUCTIVE_OPERATIONS
        mock_repo.get_allowlist_for_tenant.return_value = malicious_allowlist
        
        result = await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, operation)
        
        assert result is False

    async def test_017_tenant_extended_allowlist_custom_operation(self, mcp_gateway, mock_repo):
        """Tests a tenant with a custom, extended allowlist."""
        tenant_id = "extended_tenant"
        custom_operation = "custom_view_financials"
        extended_list = self.ALLOWED_OPERATIONS + [custom_operation]
        
        mock_repo.get_allowlist_for_tenant.side_effect = lambda t: extended_list if t == tenant_id else self.ALLOWED_OPERATIONS

        # The tenant with the extended list should be allowed
        result_extended = await mcp_gateway.is_operation_allowed(tenant_id, custom_operation)
        assert result_extended is True

        # The default tenant should be denied
        result_default = await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, custom_operation)
        assert result_default is False

    async def test_018_tenant_restricted_allowlist_blocked(self, mcp_gateway, mock_repo):
        """Tests a tenant with a more restrictive allowlist."""
        tenant_id = "restricted_tenant"
        restricted_list = ["view_projects_summary", "view_alerts_active"]
        
        mock_repo.get_allowlist_for_tenant.return_value = restricted_list
        
        # This operation is in the standard list but NOT the restricted one
        blocked_operation = "trigger_recalc"
        
        result = await mcp_gateway.is_operation_allowed(tenant_id, blocked_operation)
        assert result is False

    async def test_edge_001_empty_operation_name(self, mcp_gateway, mock_repo):
        """Tests that an empty operation name is not allowed."""
        mock_repo.get_allowlist_for_tenant.return_value = self.ALLOWED_OPERATIONS
        
        with pytest.raises(ValueError, match="Operation name cannot be empty or None"):
            await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, "")

    async def test_edge_002_null_tenant_id(self, mcp_gateway, mock_repo):
        """Tests that a null tenant ID raises a ValueError."""
        with pytest.raises(ValueError, match="Tenant ID cannot be empty or None"):
            await mcp_gateway.is_operation_allowed(None, "view_projects_summary")

    async def test_edge_003_case_insensitive_operation(self, mcp_gateway, mock_repo):
        """Tests that operations are matched in a case-insensitive manner."""
        mock_repo.get_allowlist_for_tenant.return_value = self.ALLOWED_OPERATIONS
        
        # Test with uppercase
        result = await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, "VIEW_PROJECTS_SUMMARY")
        assert result is True

    async def test_edge_004_whitespace_in_operation(self, mcp_gateway, mock_repo):
        """Tests that leading/trailing whitespace is handled."""
        mock_repo.get_allowlist_for_tenant.return_value = self.ALLOWED_OPERATIONS
        
        result = await mcp_gateway.is_operation_allowed(self.DEFAULT_TENANT_ID, "  view_projects_summary  ")
        assert result is True
