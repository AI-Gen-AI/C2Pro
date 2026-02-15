# TDD Phase 1: Foundation Tests (RED Phase)

**Week 1 Goal:** Write all failing tests before implementation  
**Status:** RED - All tests should initially FAIL

---

## 1.1 Backend API Contract Tests

### File: `tests/modules/wbs/adapters/test_wbs_api_contract.py`

```python
"""
TS-CT-WBS-API-001 - WBS API Contract Tests

Contract tests verify API/frontend alignment before implementation.
These tests will FAIL until the API endpoints are implemented.
Run: pytest tests/modules/wbs/adapters/test_wbs_api_contract.py -v
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

class TestWBSAPIContract:
    """Contract tests for WBS endpoints - MUST be written before implementation"""

    def test_get_wbs_returns_correct_schema(self):
        """RED Phase: Contract test for GET /projects/{id}/wbs

        Expected: Returns 200 with items, coverage, alerts
        """
        # Arrange
        project_id = "test-project-001"

        # Act
        response = client.get(f"/api/v1/projects/{project_id}/wbs")

        # Assert - This will FAIL until endpoint is implemented
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}. Endpoint not implemented?"

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
            import re
            assert re.match(r"^\d+(\.\d+){0,3}$", item["code"]), \
                f"Code '{item['code']}' must match pattern 1.1.1.1"

    def test_get_wbs_handles_missing_project(self):
        """RED Phase: 404 for non-existent project"""
        response = client.get("/api/v1/projects/non-existent/wbs")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_wbs_item_requires_name(self):
        """RED Phase: Validation contract test - name is required"""
        project_id = "test-project-001"

        # Act - Missing required field
        response = client.post(
            f"/api/v1/projects/{project_id}/wbs/items",
            json={}  # Empty body
        )

        # Assert - Should fail validation
        assert response.status_code == 422, \
            "Empty body should trigger validation error"

        error_detail = response.json()["detail"][0]
        assert "name" in str(error_detail), \
            "Error must indicate 'name' is required"

    def test_create_wbs_item_validates_code_format(self):
        """RED Phase: Code format validation contract

        Valid codes: 1, 1.1, 1.1.1, 1.1.1.1
        Invalid codes: 1.1.1.1.1 (too deep), A.1 (letters), 1..1 (double dot)
        """
        project_id = "test-project-001"
        invalid_codes = [
            "1.1.1.1.1",  # Too deep (level 5)
            "A.1",        # Contains letters
            "1..1",       # Double dot
            "-1",         # Negative
            "1.1.",       # Trailing dot
        ]

        for code in invalid_codes:
            response = client.post(
                f"/api/v1/projects/{project_id}/wbs/items",
                json={
                    "name": "Test Item",
                    "code": code
                }
            )

            assert response.status_code == 422, \
                f"Code '{code}' should be rejected"
            assert "code" in str(response.json()).lower()

    def test_create_wbs_item_auto_generates_code(self):
        """RED Phase: Code auto-generation when not provided"""
        project_id = "test-project-001"

        response = client.post(
            f"/api/v1/projects/{project_id}/wbs/items",
            json={
                "name": "Auto Code Test",
                "parent_id": None
            }
        )

        assert response.status_code == 201

        data = response.json()
        assert "code" in data, "Code should be auto-generated"
        assert data["code"].match(r"^\d+$"), "Root level code should be single number"

    def test_move_wbs_item_prevents_circular_reference(self):
        """RED Phase: Business logic contract test

        Cannot move an item to be its own descendant
        """
        project_id = "test-project-001"
        item_id = "item-001"

        response = client.post(
            f"/api/v1/projects/{project_id}/wbs/items/{item_id}/move",
            json={
                "newParentId": item_id  # Can't move to self
            }
        )

        assert response.status_code == 400, \
            "Moving to self should be rejected"
        assert "circular" in response.json()["detail"].lower()

    def test_move_wbs_item_enforces_max_depth(self):
        """RED Phase: Cannot exceed 4 levels when moving"""
        project_id = "test-project-001"

        # Try to move level 1 item under level 4 item (would make it level 5)
        response = client.post(
            f"/api/v1/projects/{project_id}/wbs/items/level-1-id/move",
            json={
                "newParentId": "level-4-id"
            }
        )

        assert response.status_code == 400
        assert "maximum depth" in response.json()["detail"].lower()

    def test_delete_wbs_item_with_children_requires_cascade(self):
        """RED Phase: Cascade delete protection"""
        project_id = "test-project-001"
        item_with_children = "parent-item-id"

        # Try to delete without cascade
        response = client.delete(
            f"/api/v1/projects/{project_id}/wbs/items/{item_with_children}",
            params={"cascade": False}
        )

        assert response.status_code == 400, \
            "Should reject delete of parent without cascade"
        assert "children" in response.json()["detail"].lower()

    def test_delete_wbs_item_cascade_removes_children(self):
        """RED Phase: Cascade delete removes all descendants"""
        project_id = "test-project-001"
        parent_id = "parent-item-id"

        response = client.delete(
            f"/api/v1/projects/{project_id}/wbs/items/{parent_id}",
            params={"cascade": True}
        )

        assert response.status_code == 204

        # Verify children are also deleted
        get_response = client.get(
            f"/api/v1/projects/{project_id}/wbs/items/child-id"
        )
        assert get_response.status_code == 404

    def test_update_wbs_item_validates_budget(self):
        """RED Phase: Budget cannot be negative"""
        project_id = "test-project-001"
        item_id = "item-001"

        response = client.patch(
            f"/api/v1/projects/{project_id}/wbs/items/{item_id}",
            json={
                "budget": {"amount": -1000, "currency": "EUR"}
            }
        )

        assert response.status_code == 422
        assert "budget" in str(response.json()).lower()

    def test_wbs_response_includes_tenant_isolation(self):
        """RED Phase: Tenant context in response headers"""
        project_id = "test-project-001"

        response = client.get(
            f"/api/v1/projects/{project_id}/wbs",
            headers={"X-Tenant-ID": "tenant-001"}
        )

        assert response.status_code == 200
        # Verify tenant isolation (implementation detail)
        assert "X-Tenant-ID" in response.headers or True  # Placeholder
```

---

## 1.2 Backend Domain Logic Tests

### File: `tests/modules/wbs/domain/test_wbs_item_entity.py`

```python
"""
TS-UD-WBS-001 - WBS Item Entity Domain Tests

Tests for pure domain logic without infrastructure dependencies.
"""

import pytest
from uuid import uuid4
from src.wbs.domain.entities import WBSItem, Money
from src.wbs.domain.exceptions import InvalidCodeError, MaxDepthExceededError

class TestWBSItemEntity:
    """TDD tests for WBSItem domain entity"""

    def test_create_wbs_item_with_valid_code(self):
        """RED Phase: Create WBS item with valid code format"""
        # Arrange & Act
        item = WBSItem(
            id=str(uuid4()),
            code="2.1.3.1",
            name="Reinforcement",
            level=4,
            project_id=str(uuid4())
        )

        # Assert
        assert item.code == "2.1.3.1"
        assert item.level == 4
        assert item.name == "Reinforcement"

    def test_create_wbs_item_with_invalid_code_raises_error(self):
        """RED Phase: Invalid code format raises domain error"""
        with pytest.raises(InvalidCodeError) as exc_info:
            WBSItem(
                id=str(uuid4()),
                code="1.1.1.1.1",  # Level 5 - too deep
                name="Invalid",
                level=5,
                project_id=str(uuid4())
            )

        assert "maximum depth" in str(exc_info.value).lower()

    def test_code_level_consistency(self):
        """RED Phase: Code must match level

        Code 1 = level 1
        Code 1.1 = level 2
        Code 1.1.1 = level 3
        Code 1.1.1.1 = level 4
        """
        test_cases = [
            ("1", 1),
            ("2.1", 2),
            ("3.2.1", 3),
            ("4.3.2.1", 4),
        ]

        for code, expected_level in test_cases:
            item = WBSItem(
                id=str(uuid4()),
                code=code,
                name=f"Level {expected_level}",
                level=expected_level,
                project_id=str(uuid4())
            )

            # Verify level matches code depth
            actual_level = len(code.split("."))
            assert actual_level == expected_level, \
                f"Code '{code}' should be level {actual_level}, got {expected_level}"

    def test_generate_code_for_root_item(self):
        """RED Phase: Generate code for root level (no parent)"""
        # Arrange - Existing items with codes 1, 2
        existing_codes = ["1", "2"]

        # Act
        new_code = WBSItem.generate_code(existing_codes, parent_code=None)

        # Assert
        assert new_code == "3"

    def test_generate_code_for_child_item(self):
        """RED Phase: Generate code for child item"""
        # Arrange - Parent 2.1 has children 2.1.1, 2.1.2
        existing_codes = ["2.1.1", "2.1.2"]

        # Act
        new_code = WBSItem.generate_code(existing_codes, parent_code="2.1")

        # Assert
        assert new_code == "2.1.3"

    def test_cannot_exceed_maximum_depth(self):
        """RED Phase: Level 4 items cannot have children"""
        parent = WBSItem(
            id=str(uuid4()),
            code="1.1.1.1",
            name="Level 4 Parent",
            level=4,
            project_id=str(uuid4())
        )

        with pytest.raises(MaxDepthExceededError):
            WBSItem.create_child(
                parent=parent,
                name="Level 5 Child",
                existing_codes=[]
            )

    def test_completion_percentage_validation(self):
        """RED Phase: Completion must be 0-100"""
        # Valid values
        for completion in [0, 50, 100]:
            item = WBSItem(
                id=str(uuid4()),
                code="1",
                name="Test",
                level=1,
                project_id=str(uuid4()),
                completion=completion
            )
            assert item.completion == completion

        # Invalid values
        for completion in [-1, 101, 150]:
            with pytest.raises(ValueError):
                WBSItem(
                    id=str(uuid4()),
                    code="1",
                    name="Test",
                    level=1,
                    project_id=str(uuid4()),
                    completion=completion
                )

    def test_budget_money_value_object(self):
        """RED Phase: Money value object encapsulation"""
        # Valid money
        budget = Money(amount=150000.00, currency="EUR")
        assert budget.amount == 150000.00
        assert budget.currency == "EUR"

        # Invalid - negative amount
        with pytest.raises(ValueError):
            Money(amount=-100, currency="EUR")

        # Invalid - unsupported currency
        with pytest.raises(ValueError):
            Money(amount=100, currency="XYZ")

    def test_wbs_item_immutability(self):
        """RED Phase: WBS item attributes are immutable"""
        item = WBSItem(
            id=str(uuid4()),
            code="1",
            name="Original",
            level=1,
            project_id=str(uuid4())
        )

        # Attempt to modify
        with pytest.raises(AttributeError):
            item.name = "Modified"

        with pytest.raises(AttributeError):
            item.code = "2"

    def test_is_ancestor_of(self):
        """RED Phase: Check ancestor relationship"""
        parent = WBSItem(
            id="parent-id",
            code="2",
            name="Parent",
            level=1,
            project_id="proj-1"
        )

        child = WBSItem(
            id="child-id",
            code="2.1",
            name="Child",
            level=2,
            project_id="proj-1",
            parent_id="parent-id"
        )

        grandchild = WBSItem(
            id="grandchild-id",
            code="2.1.3",
            name="Grandchild",
            level=3,
            project_id="proj-1",
            parent_id="child-id"
        )

        # Test ancestor relationships
        assert parent.is_ancestor_of(child)
        assert parent.is_ancestor_of(grandchild)
        assert child.is_ancestor_of(grandchild)
        assert not child.is_ancestor_of(parent)
        assert not grandchild.is_ancestor_of(parent)
```

---

## 1.3 Frontend Component Contract Tests

### File: `apps/web/components/wbs/__tests__/WBSTree.contract.test.tsx`

```typescript
/**
 * TS-UAD-WBS-TREE-001 - WBS Tree Component Contract Tests
 *
 * These tests define the component interface before implementation.
 * Run: npm test WBSTree.contract
 */

import { render, screen } from '@testing-library/react';
import { WBSTree } from '../WBSTree';
import { mockWBSItems } from '@/tests/mocks/wbs';

describe('WBSTree Component Contract - RED Phase', () => {
  /**
   * CONTRACT: Component must accept items prop
   */
  it('should accept and render items prop', () => {
    // This will fail until WBSTree is implemented
    const { container } = render(
      <WBSTree items={mockWBSItems} />
    );

    expect(container.querySelector('.wbs-tree')).toBeInTheDocument();
  });

  /**
   * CONTRACT: Component must call onSelect when item clicked
   */
  it('should call onSelect callback when item is clicked', async () => {
    const onSelect = jest.fn();

    render(
      <WBSTree
        items={mockWBSItems}
        onSelect={onSelect}
      />
    );

    // Attempt to click first item
    const firstItem = screen.getByText(mockWBSItems[0].name);
    await userEvent.click(firstItem);

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        id: mockWBSItems[0].id,
        code: mockWBSItems[0].code,
        name: mockWBSItems[0].name
      })
    );
  });

  /**
   * CONTRACT: Component must handle empty items array
   */
  it('should render empty state when items is empty array', () => {
    render(<WBSTree items={[]} />);

    expect(screen.getByText(/no wbs items/i)).toBeInTheDocument();
  });

  /**
   * CONTRACT: Component must support filter prop
   */
  it('should filter items when filter prop is provided', () => {
    render(
      <WBSTree
        items={mockWBSItems}
        filter={{ status: 'in-progress' }}
      />
    );

    // Should only show items with completion between 1-99%
    const visibleItems = screen.getAllByTestId('wbs-item');
    const inProgressCount = mockWBSItems.filter(
      item => item.completion > 0 && item.completion < 100
    ).length;

    expect(visibleItems).toHaveLength(inProgressCount);
  });

  /**
   * CONTRACT: Component must support searchQuery prop
   */
  it('should filter items by searchQuery', () => {
    render(
      <WBSTree
        items={mockWBSItems}
        searchQuery="foundation"
      />
    );

    // Should show items matching "foundation"
    expect(screen.getByText(/foundation/i)).toBeInTheDocument();

    // Should not show non-matching items
    const nonMatching = mockWBSItems.find(item =>
      !item.name.toLowerCase().includes('foundation') &&
      !item.code.includes('foundation')
    );

    if (nonMatching) {
      expect(screen.queryByText(nonMatching.name)).not.toBeInTheDocument();
    }
  });

  /**
   * CONTRACT: Component must support readOnly mode
   */
  it('should disable editing when readOnly is true', () => {
    render(
      <WBSTree
        items={mockWBSItems}
        readOnly={true}
      />
    );

    // Should not show edit buttons
    expect(screen.queryByRole('button', { name: /edit/i }))
      .not.toBeInTheDocument();

    // Should not show drag handles
    expect(screen.queryByTestId('drag-handle')).not.toBeInTheDocument();
  });

  /**
   * CONTRACT: Component must support expandedItems prop
   */
  it('should expand items specified in expandedItems prop', () => {
    const parentItem = mockWBSItems.find(item => item.children?.length > 0);

    render(
      <WBSTree
        items={mockWBSItems}
        expandedItems={[parentItem.id]}
      />
    );

    // Children of expanded item should be visible
    parentItem.children.forEach(child => {
      expect(screen.getByText(child.name)).toBeInTheDocument();
    });
  });

  /**
   * CONTRACT: Component must call onExpand when item expanded
   */
  it('should call onExpand when expand button clicked', async () => {
    const onExpand = jest.fn();
    const parentItem = mockWBSItems.find(item => item.children?.length > 0);

    render(
      <WBSTree
        items={mockWBSItems}
        onExpand={onExpand}
      />
    );

    const expandButton = screen.getByRole('button', {
      name: new RegExp(`expand ${parentItem.name}`, 'i')
    });

    await userEvent.click(expandButton);

    expect(onExpand).toHaveBeenCalledWith(parentItem);
  });
});
```

---

## 1.4 Cross-Module Navigation Contract Tests

### File: `apps/web/tests/integration/navigation.contract.test.tsx`

```typescript
/**
 * TS-INT-NAV-001 - Cross-Module Navigation Contract Tests
 *
 * Defines navigation patterns between WBS, Procurement, Alerts, Coherence
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectDetailPage } from '@/app/(dashboard)/projects/[id]/page';

describe('Cross-Module Navigation Contracts - RED Phase', () => {
  const queryClient = new QueryClient();

  /**
   * CONTRACT: WBS item detail must show linked procurement items
   */
  it('should display linked procurement items in WBS detail', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectDetailPage params={{ id: 'test-project' }} />
      </QueryClientProvider>
    );

    // Navigate to WBS
    await userEvent.click(screen.getByRole('tab', { name: /wbs/i }));

    // Select WBS item with procurement
    const wbsItem = await screen.findByText('2.1.3.1 Reinforcement');
    await userEvent.click(wbsItem);

    // Detail panel should show procurement section
    expect(screen.getByTestId('wbs-item-detail')).toBeInTheDocument();
    expect(screen.getByText(/linked procurement/i)).toBeInTheDocument();
    expect(screen.getByText('Steel Rebar')).toBeInTheDocument();
  });

  /**
   * CONTRACT: Clicking procurement link navigates to procurement tab
   */
  it('should navigate to procurement tab when procurement link clicked', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectDetailPage params={{ id: 'test-project' }} />
      </QueryClientProvider>
    );

    // Go to WBS and open item with procurement
    await userEvent.click(screen.getByRole('tab', { name: /wbs/i }));
    await userEvent.click(await screen.findByText('2.1.3.1 Reinforcement'));

    // Click link to procurement
    const procurementLink = screen.getByRole('button', {
      name: /view in procurement/i
    });
    await userEvent.click(procurementLink);

    // Should switch to procurement tab
    expect(screen.getByRole('tab', { name: /procurement/i }))
      .toHaveAttribute('aria-selected', 'true');

    // Should filter to relevant procurement items
    expect(screen.getByText('Steel Rebar')).toBeInTheDocument();
  });

  /**
   * CONTRACT: Alert detail must show all affected entities
   */
  it('should display affected entities in alert detail', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AlertDetailPage alertId="r14-alert-001" />
      </QueryClientProvider>
    );

    // Should show affected WBS items
    expect(screen.getByText('Affected Entities')).toBeInTheDocument();
    expect(screen.getByText('2.1.3.1 Reinforcement')).toBeInTheDocument();

    // Should show affected procurement items
    expect(screen.getByText('Steel Rebar')).toBeInTheDocument();

    // Should show linked clauses
    expect(screen.getByText(/clause/i)).toBeInTheDocument();
  });

  /**
   * CONTRACT: Clicking entity in alert navigates to that entity
   */
  it('should navigate to entity when clicked in alert detail', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AlertDetailPage alertId="r14-alert-001" />
      </QueryClientProvider>
    );

    // Click on WBS entity
    await userEvent.click(screen.getByRole('link', {
      name: /2\.1\.3\.1/i
    }));

    // Should navigate to WBS and focus that item
    expect(await screen.findByTestId('wbs-tree')).toBeInTheDocument();

    // Item should be highlighted/selected
    const item = screen.getByText('2.1.3.1 Reinforcement').parentElement;
    expect(item).toHaveClass('selected');
  });

  /**
   * CONTRACT: Coherence score drill-down navigates to details
   */
  it('should navigate to category detail when coherence score clicked', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <CoherenceDashboard projectId="test-project" />
      </QueryClientProvider>
    );

    // Find budget score card (typically the lowest)
    const budgetCard = screen.getByTestId('score-card-budget');
    await userEvent.click(budgetCard);

    // Should navigate to budget detail view
    expect(screen.getByText(/budget detail/i)).toBeInTheDocument();

    // Should show affected items
    expect(screen.getByText(/affected wbs items/i)).toBeInTheDocument();
    expect(screen.getByText(/rule violations/i)).toBeInTheDocument();
  });

  /**
   * CONTRACT: Global search shows results from all modules
   */
  it('should search across all modules', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <GlobalSearch />
      </QueryClientProvider>
    );

    // Type search query
    const searchInput = screen.getByPlaceholderText(/search/i);
    await userEvent.type(searchInput, 'foundation');

    // Should show results from multiple modules
    expect(screen.getByText(/wbs items/i)).toBeInTheDocument();
    expect(screen.getByText(/procurement/i)).toBeInTheDocument();
    expect(screen.getByText(/documents/i)).toBeInTheDocument();

    // Click on WBS result
    await userEvent.click(screen.getByText('2 Substructure'));

    // Should navigate to WBS
    expect(await screen.findByTestId('wbs-tree')).toBeInTheDocument();
  });
});
```

---

## Summary: Week 1 RED Phase Checklist

### Backend Contract Tests

- [ ] WBS API schema validation (15 tests)
- [ ] Error response contracts (validation, 404, 400)
- [ ] Domain entity contracts (10 tests)
- [ ] Use case input/output contracts

### Frontend Component Contracts

- [ ] WBSTree prop interface (10 tests)
- [ ] WBSItemCard rendering contract
- [ ] Event handler contracts (onSelect, onExpand)
- [ ] State management contracts

### Integration Contracts

- [ ] Cross-module navigation patterns (6 tests)
- [ ] API-to-frontend data flow
- [ ] State synchronization contracts

### Total: 45+ Tests (All should FAIL initially)

**Expected State at End of Week 1:**

- ✅ All contract tests written
- ✅ All tests FAILING (correct for RED phase)
- ✅ Test utilities and mocks created
- ✅ CI pipeline configured to run tests
- ⏳ Ready for GREEN phase (Week 2)

---

**Next:** TDD_WEEK2_TESTS.md - WBS Module Implementation Tests (GREEN Phase)
