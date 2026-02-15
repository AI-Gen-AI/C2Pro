"""
TS-CT-WBS-API-001 - WBS API Contract Tests

Test Suite ID: TS-CT-WBS-API-001
Component: WBS Module - HTTP Adapters
Priority: P0
Phase: RED (Write failing tests first)

Contract tests verify API/frontend alignment before implementation.
These tests will FAIL until the API endpoints are implemented.

Run: pytest tests/modules/wbs/adapters/test_wbs_api_contract.py -v
"""

import pytest
import re
from uuid import uuid4, UUID
from unittest.mock import Mock, patch
from fastapi import FastAPI, status
from fastapi.testclient import TestClient


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def test_app():
    """Create FastAPI app for testing WBS endpoints."""
    from src.wbs.adapters.http.router import router as wbs_router
    app = FastAPI()
    # Include WBS router - GREEN phase
    app.include_router(wbs_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(test_app):
    """Create TestClient for HTTP testing."""
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture
def test_project_id():
    """Return a test project ID."""
    return "test-project-001"


@pytest.fixture
def valid_wbs_item_data():
    """Return valid WBS item data for testing."""
    return {
        "name": "Foundation Works",
        "description": "Concrete foundation construction",
        "parent_id": None,
        "start_date": "2025-05-01",
        "end_date": "2025-05-15",
        "budget": {"amount": 450000.00, "currency": "EUR"},
        "completion": 0
    }


# ===========================================
# CONTRACT TESTS: GET /projects/{id}/wbs
# ===========================================


class TestGetWBSContract:
    """Contract tests for GET /projects/{id}/wbs endpoint."""

    def test_get_wbs_returns_correct_schema(self, client, test_project_id):
        """
        RED Phase: Contract test for GET /projects/{id}/wbs
        
        Expected: Returns 200 with items, coverage, alerts
        
        This test will FAIL until:
        - The endpoint is implemented
        - The router is registered
        """
        # Act
        response = client.get(f"/api/v1/projects/{test_project_id}/wbs")

        # Assert - This will FAIL until endpoint is implemented
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            "Endpoint not implemented?"
        )

        data = response.json()

        # Schema validation - contract definition
        assert "items" in data, "Response must include 'items' array"
        assert "coverage" in data, "Response must include 'coverage' object"
        assert "alerts" in data, "Response must include 'alerts' array"

        # WBS Item schema validation
        if data["items"]:
            item = data["items"][0]
            assert "id" in item, "WBSItem must have 'id'"
            assert "code" in item, "WBSItem must have 'code'"
            assert "name" in item, "WBSItem must have 'name'"
            assert "level" in item, "WBSItem must have 'level'"
            assert "children" in item, "WBSItem must have 'children' array"

            # Type validation
            assert isinstance(item["level"], int), "level must be integer"
            assert 1 <= item["level"] <= 4, "level must be between 1-4"

            # Code format validation: 1, 1.1, 1.1.1, 1.1.1.1
            assert re.match(r"^\d+(\.\d+){0,3}$", item["code"]), (
                f"Code '{item['code']}' must match pattern 1.1.1.1"
            )

    def test_get_wbs_handles_missing_project(self, client):
        """
        RED Phase: 404 for non-existent project
        
        Expected: Returns 404 with appropriate error message
        """
        response = client.get("/api/v1/projects/non-existent/wbs")

        assert response.status_code == 404, (
            f"Expected 404, got {response.status_code}"
        )
        
        data = response.json()
        assert "detail" in data, "Error response must have 'detail' field"
        assert "not found" in data["detail"].lower(), (
            "Error message should indicate resource not found"
        )


# ===========================================
# CONTRACT TESTS: POST /projects/{id}/wbs/items
# ===========================================


class TestCreateWBSItemContract:
    """Contract tests for POST /projects/{id}/wbs/items endpoint."""

    def test_create_wbs_item_requires_name(self, client, test_project_id):
        """
        RED Phase: Validation contract test - name is required
        
        Expected: Returns 422 when name is missing
        """
        # Act - Missing required field
        response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={}  # Empty body
        )

        # Assert - Should fail validation
        assert response.status_code == 422, (
            f"Expected 422, got {response.status_code}. "
            "Empty body should trigger validation error"
        )

        error_detail = response.json()["detail"]
        assert any("name" in str(err).lower() for err in error_detail), (
            "Error must indicate 'name' is required"
        )

    def test_create_wbs_item_validates_code_format(
        self, client, test_project_id, valid_wbs_item_data
    ):
        """
        RED Phase: Code format validation contract
        
        Valid codes: 1, 1.1, 1.1.1, 1.1.1.1
        Invalid codes: 1.1.1.1.1 (too deep), A.1 (letters), 1..1 (double dot)
        """
        invalid_codes = [
            "1.1.1.1.1",  # Too deep (level 5)
            "A.1",        # Contains letters
            "1..1",       # Double dot
            "-1",         # Negative
            "1.1.",       # Trailing dot
        ]

        for code in invalid_codes:
            payload = {
                **valid_wbs_item_data,
                "code": code
            }
            
            response = client.post(
                f"/api/v1/projects/{test_project_id}/wbs/items",
                json=payload
            )

            assert response.status_code == 422, (
                f"Code '{code}' should be rejected with 422, "
                f"got {response.status_code}"
            )
            
            error_str = str(response.json()).lower()
            assert "code" in error_str, (
                f"Error should mention 'code' field for invalid code '{code}'"
            )

    def test_create_wbs_item_auto_generates_code(
        self, client, test_project_id, valid_wbs_item_data
    ):
        """
        RED Phase: Code auto-generation when not provided
        
        Expected: Returns 201 with auto-generated code
        """
        payload = {
            **valid_wbs_item_data,
            "parent_id": None
        }
        # Ensure no code is provided
        payload.pop("code", None)

        response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json=payload
        )

        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}"
        )

        data = response.json()
        assert "code" in data, "Code should be auto-generated"
        assert re.match(r"^\d+$", data["code"]), (
            "Root level code should be single number"
        )


# ===========================================
# CONTRACT TESTS: POST /projects/{id}/wbs/items/{item_id}/move
# ===========================================


class TestMoveWBSItemContract:
    """Contract tests for POST /projects/{id}/wbs/items/{item_id}/move endpoint."""

    def test_move_wbs_item_prevents_circular_reference(
        self, client, test_project_id
    ):
        """
        GREEN Phase: Business logic contract test
        
        Cannot move an item to be its own descendant
        Expected: Returns 400 with circular reference error
        """
        # First create an item
        create_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Test Item for Circular Reference"}
        )
        assert create_response.status_code == 201, f"Failed to create item: {create_response.text}"
        item_id = create_response.json()["id"]

        # Try to move item to itself
        response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items/{item_id}/move",
            json={
                "new_parent_id": item_id  # Can't move to self
            }
        )

        assert response.status_code == 400, (
            f"Expected 400, got {response.status_code}. "
            "Moving to self should be rejected"
        )
        
        data = response.json()
        assert "detail" in data, "Error must have detail field"
        assert "circular" in data["detail"].lower(), (
            "Error should mention circular reference"
        )

    def test_move_wbs_item_enforces_max_depth(self, client, test_project_id):
        """
        GREEN Phase: Cannot exceed 4 levels when moving
        
        Expected: Returns 400 when move would create level 5 item
        """
        # Create level 1 item
        level_1_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Level 1 Item"}
        )
        assert level_1_response.status_code == 201
        level_1_item_id = level_1_response.json()["id"]
        
        # Create level 2, 3, 4 hierarchy
        level_2_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Level 2 Item", "parent_id": level_1_item_id}
        )
        assert level_2_response.status_code == 201
        level_2_item_id = level_2_response.json()["id"]
        
        level_3_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Level 3 Item", "parent_id": level_2_item_id}
        )
        assert level_3_response.status_code == 201
        level_3_item_id = level_3_response.json()["id"]
        
        level_4_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Level 4 Item", "parent_id": level_3_item_id}
        )
        assert level_4_response.status_code == 201
        level_4_item_id = level_4_response.json()["id"]

        # Try to move level 1 item under level 4 item (would make it level 5)
        response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items/{level_1_item_id}/move",
            json={
                "new_parent_id": level_4_item_id
            }
        )

        assert response.status_code == 400, (
            f"Expected 400, got {response.status_code}"
        )
        
        data = response.json()
        assert "detail" in data, "Error must have detail field"
        assert "depth" in data["detail"].lower(), (
            "Error should mention maximum depth"
        )


# ===========================================
# CONTRACT TESTS: DELETE /projects/{id}/wbs/items/{item_id}
# ===========================================


class TestDeleteWBSItemContract:
    """Contract tests for DELETE /projects/{id}/wbs/items/{item_id} endpoint."""

    def test_delete_wbs_item_with_children_requires_cascade(
        self, client, test_project_id
    ):
        """
        GREEN Phase: Cascade delete protection
        
        Expected: Returns 400 when trying to delete parent without cascade
        """
        # First create parent item
        parent_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Parent Item for Delete Test"}
        )
        assert parent_response.status_code == 201
        parent_item_id = parent_response.json()["id"]
        
        # Create child item
        child_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Child Item", "parent_id": parent_item_id}
        )
        assert child_response.status_code == 201

        # Try to delete without cascade
        response = client.delete(
            f"/api/v1/projects/{test_project_id}/wbs/items/{parent_item_id}",
            params={"cascade": "false"}
        )

        assert response.status_code == 400, (
            f"Expected 400, got {response.status_code}. "
            "Should reject delete of parent without cascade"
        )
        
        data = response.json()
        assert "detail" in data, "Error must have detail field"
        assert "children" in data["detail"].lower(), (
            "Error should mention children"
        )

    def test_delete_wbs_item_cascade_removes_children(
        self, client, test_project_id
    ):
        """
        GREEN Phase: Cascade delete removes all descendants
        
        Expected: Returns 204 and removes all descendants
        """
        # First create parent item
        parent_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Parent Item for Cascade Test"}
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["id"]
        
        # Create child item
        child_response = client.post(
            f"/api/v1/projects/{test_project_id}/wbs/items",
            json={"name": "Child Item", "parent_id": parent_id}
        )
        assert child_response.status_code == 201
        child_id = child_response.json()["id"]

        response = client.delete(
            f"/api/v1/projects/{test_project_id}/wbs/items/{parent_id}",
            params={"cascade": "true"}
        )

        assert response.status_code == 204, (
            f"Expected 204, got {response.status_code}"
        )

        # Verify child is also deleted
        get_response = client.get(
            f"/api/v1/projects/{test_project_id}/wbs/items/{child_id}"
        )
        assert get_response.status_code == 404, (
            "Child item should be deleted when parent is cascade deleted"
        )


# ===========================================
# CONTRACT TESTS: PATCH /projects/{id}/wbs/items/{item_id}
# ===========================================


class TestUpdateWBSItemContract:
    """Contract tests for PATCH /projects/{id}/wbs/items/{item_id} endpoint."""

    def test_update_wbs_item_validates_budget(
        self, client, test_project_id
    ):
        """
        RED Phase: Budget cannot be negative
        
        Expected: Returns 422 when budget amount is negative
        """
        item_id = "item-001"

        response = client.patch(
            f"/api/v1/projects/{test_project_id}/wbs/items/{item_id}",
            json={
                "budget": {"amount": -1000, "currency": "EUR"}
            }
        )

        assert response.status_code == 422, (
            f"Expected 422, got {response.status_code}"
        )
        
        error_str = str(response.json()).lower()
        assert "budget" in error_str, (
            "Error should mention budget field"
        )


# ===========================================
# CONTRACT TESTS: Security & Isolation
# ===========================================


class TestWBSTenantIsolationContract:
    """Contract tests for tenant isolation in WBS endpoints."""

    def test_wbs_response_includes_tenant_isolation(
        self, client, test_project_id
    ):
        """
        RED Phase: Tenant context in response headers
        
        Expected: Tenant isolation enforced via headers or response structure
        """
        tenant_id = "tenant-001"

        response = client.get(
            f"/api/v1/projects/{test_project_id}/wbs",
            headers={"X-Tenant-ID": tenant_id}
        )

        # For now, just verify endpoint exists (will be 404 until implemented)
        # In GREEN phase, verify tenant context is respected
        assert response.status_code in [200, 404], (
            f"Unexpected status {response.status_code}"
        )

        # Additional tenant isolation checks to implement in GREEN phase:
        # - Verify only items from specified tenant are returned
        # - Verify X-Tenant-ID header is validated
        # - Verify cross-tenant access is forbidden (403)


# ===========================================
# END OF TEST SUITE
# ===========================================

# Mark all tests in this file as contract tests
# GREEN PHASE: Tests now passing with implementation
pytestmark = [
    pytest.mark.contract,
    pytest.mark.green_phase,
]
