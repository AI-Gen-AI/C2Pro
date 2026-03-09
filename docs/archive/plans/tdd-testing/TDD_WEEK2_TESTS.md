# TDD Phase 2: WBS Module Tests (GREEN Phase)

**Week 2 Goal:** Implement WBS features to make Week 1 tests PASS  
**Status:** GREEN - Write minimal code to pass tests

---

## 2.1 User Story Test Matrix

### Story 1: Filter WBS by Completion Status

**TS-UAD-WBS-FILTER-001**

```typescript
// apps/web/hooks/__tests__/useWbsFilter.test.ts

import { renderHook } from "@testing-library/react-hooks";
import { useWbsFilter } from "../useWbsFilter";
import { mockWBSItems } from "@/tests/mocks/wbs";

describe("Story: Filter WBS by completion status - GREEN Phase", () => {
  const testCases = [
    {
      status: "not-started",
      filter: (item) => item.completion === 0,
      description: "completion = 0%",
    },
    {
      status: "in-progress",
      filter: (item) => item.completion > 0 && item.completion < 100,
      description: "completion = 1-99%",
    },
    {
      status: "complete",
      filter: (item) => item.completion === 100,
      description: "completion = 100%",
    },
  ];

  testCases.forEach(({ status, filter, description }) => {
    it(`should filter ${status} items (${description})`, () => {
      const { result } = renderHook(() =>
        useWbsFilter(mockWBSItems, { status }),
      );

      const expectedItems = mockWBSItems.filter(filter);

      expect(result.current.filteredItems).toHaveLength(expectedItems.length);

      result.current.filteredItems.forEach((item) => {
        expect(filter(item)).toBe(true);
      });
    });
  });

  it("should update URL query params when filter changes", () => {
    const pushStateSpy = jest.spyOn(window.history, "pushState");

    const { result } = renderHook(() =>
      useWbsFilter(mockWBSItems, { status: "in-progress" }),
    );

    // Change filter
    result.current.setFilter({ status: "complete" });

    expect(pushStateSpy).toHaveBeenCalledWith(
      expect.anything(),
      "",
      expect.stringContaining("status=complete"),
    );
  });

  it("should read filter from URL on mount", () => {
    // Set URL params
    window.history.pushState({}, "", "?status=in-progress");

    const { result } = renderHook(() => useWbsFilter(mockWBSItems));

    expect(result.current.filter.status).toBe("in-progress");

    // Cleanup
    window.history.pushState({}, "", "/");
  });

  it("should persist filter in localStorage", () => {
    const { result } = renderHook(() =>
      useWbsFilter(mockWBSItems, { status: "complete" }),
    );

    // Check localStorage
    expect(localStorage.getItem("wbs-filter")).toBe(
      JSON.stringify({ status: "complete" }),
    );

    // On re-render, should restore from localStorage
    const { result: result2 } = renderHook(() => useWbsFilter(mockWBSItems));
    expect(result2.current.filter.status).toBe("complete");
  });

  it("should combine multiple filters", () => {
    const { result } = renderHook(() =>
      useWbsFilter(mockWBSItems, {
        status: "in-progress",
        hasAlerts: true,
      }),
    );

    result.current.filteredItems.forEach((item) => {
      expect(item.completion).toBeGreaterThan(0);
      expect(item.completion).toBeLessThan(100);
      expect(item.alerts?.length).toBeGreaterThan(0);
    });
  });
});
```

### Story 2: Search WBS Items

**TS-UAD-WBS-SEARCH-001**

```typescript
// apps/web/hooks/__tests__/useWbsSearch.test.ts

import { renderHook } from "@testing-library/react-hooks";
import { useWbsSearch } from "../useWbsSearch";
import { mockWBSItems } from "@/tests/mocks/wbs";

describe("Story: Search WBS items - GREEN Phase", () => {
  it("should search by name (case insensitive)", () => {
    const { result } = renderHook(() =>
      useWbsSearch(mockWBSItems, "foundation"),
    );

    expect(result.current.results.length).toBeGreaterThan(0);

    result.current.results.forEach((item) => {
      const match =
        item.name.toLowerCase().includes("foundation") ||
        item.description?.toLowerCase().includes("foundation");
      expect(match).toBe(true);
    });
  });

  it("should search by code", () => {
    const { result } = renderHook(() => useWbsSearch(mockWBSItems, "2.1.3"));

    // Should match 2.1.3, 2.1.3.1, 2.1.3.2, etc.
    expect(
      result.current.results.every((item) => item.code.startsWith("2.1.3")),
    ).toBe(true);
  });

  it("should search by description", () => {
    const { result } = renderHook(() =>
      useWbsSearch(mockWBSItems, "concrete pour"),
    );

    expect(result.current.results.length).toBeGreaterThan(0);
  });

  it("should highlight matching text", () => {
    const { result } = renderHook(() =>
      useWbsSearch(mockWBSItems, "reinforcement"),
    );

    // Check that highlighted text is marked
    const firstResult = result.current.results[0];
    expect(firstResult.highlightedName).toContain("<mark>");
    expect(firstResult.highlightedName).toContain("</mark>");
  });

  it("should debounce search input", async () => {
    jest.useFakeTimers();

    const { result, rerender } = renderHook(
      ({ query }) => useWbsSearch(mockWBSItems, query),
      { initialProps: { query: "" } },
    );

    // Type quickly
    rerender({ query: "f" });
    rerender({ query: "fo" });
    rerender({ query: "fou" });
    rerender({ query: "foun" });
    rerender({ query: "found" });

    // Should not search yet
    expect(result.current.isSearching).toBe(false);

    // Wait for debounce
    jest.advanceTimersByTime(300);

    // Now should search
    expect(result.current.isSearching).toBe(true);

    jest.useRealTimers();
  });

  it('should show "no results" message', () => {
    const { result } = renderHook(() =>
      useWbsSearch(mockWBSItems, "xyz123nonexistent"),
    );

    expect(result.current.results).toHaveLength(0);
    expect(result.current.hasNoResults).toBe(true);
  });

  it("should fuzzy search with typos", () => {
    const { result } = renderHook(() =>
      useWbsSearch(mockWBSItems, "fondation", { fuzzy: true }),
    );

    // Should match "foundation" despite typo
    expect(result.current.results.length).toBeGreaterThan(0);
  });
});
```

### Story 3: Color-Code by Alert Severity

**TS-UAD-WBS-COLOR-001**

```typescript
// apps/web/components/wbs/__tests__/WBSAlertBadge.test.tsx

import { render, screen } from '@testing-library/react';
import { WBSAlertBadge } from '../WBSAlertBadge';

describe('Story: Color-code by alert severity - GREEN Phase', () => {
  const alertColors = {
    none: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200' },
    low: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200' },
    medium: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-200' },
    high: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200' },
    critical: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200' },
  };

  Object.entries(alertColors).forEach(([severity, colors]) => {
    it(`should render ${severity} alerts with correct styling`, () => {
      render(<WBSAlertBadge severity={severity} count={2} />);

      const badge = screen.getByTestId('alert-badge');

      expect(badge).toHaveClass(colors.bg);
      expect(badge).toHaveClass(colors.text);
      expect(badge).toHaveClass(colors.border);
    });
  });

  it('should meet WCAG AA color contrast', () => {
    const { container } = render(
      <WBSAlertBadge severity="critical" count={5} />
    );

    // Use axe-core for accessibility testing
    expect(container).toHaveNoAccessibilityViolations();
  });

  it('should show count when multiple alerts', () => {
    render(<WBSAlertBadge severity="high" count={3} />);

    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('should show icon based on severity', () => {
    const { rerender } = render(<WBSAlertBadge severity="critical" count={1} />);

    expect(screen.getByTestId('icon-critical')).toBeInTheDocument();

    rerender(<WBSAlertBadge severity="warning" count={1} />);
    expect(screen.getByTestId('icon-warning')).toBeInTheDocument();
  });
});
```

---

## 2.2 WBS CRUD Operations Tests

### File: `tests/modules/wbs/application/test_wbs_crud.py`

```python
"""
TS-UA-WBS-CRUD-001 - WBS CRUD Use Cases Tests

TDD tests for WBS CRUD operations - GREEN Phase
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, patch
from src.wbs.application.use_cases import (
    CreateWBSItemUseCase,
    UpdateWBSItemUseCase,
    DeleteWBSItemUseCase,
    MoveWBSItemUseCase
)
from src.wbs.domain.entities import WBSItem
from src.wbs.domain.exceptions import (
    InvalidCodeError,
    MaxDepthExceededError,
    CircularReferenceError,
    ItemNotFoundError
)

class TestCreateWBSItemUseCase:
    """GREEN Phase: Make create tests pass with minimal code"""

    @pytest.fixture
    def use_case(self):
        repo = Mock()
        return CreateWBSItemUseCase(repo)

    def test_create_generates_code_for_root_item(self, use_case):
        """GREEN: Auto-generate code when not provided"""
        # Arrange
        project_id = str(uuid4())
        use_case.repo.get_by_project.return_value = [
            WBSItem(id=str(uuid4()), code="1", name="First", level=1, project_id=project_id),
            WBSItem(id=str(uuid4()), code="2", name="Second", level=1, project_id=project_id),
        ]

        request = CreateWBSItemRequest(
            project_id=project_id,
            name="Third Item",
            parent_id=None
        )

        # Act
        result = use_case.execute(request)

        # Assert
        assert result.code == "3"  # Next available root code
        assert result.level == 1
        use_case.repo.save.assert_called_once()

    def test_create_generates_child_code(self, use_case):
        """GREEN: Generate code based on parent"""
        # Arrange
        project_id = str(uuid4())
        parent_id = str(uuid4())

        use_case.repo.get_by_id.return_value = WBSItem(
            id=parent_id,
            code="2.1",
            name="Parent",
            level=2,
            project_id=project_id
        )
        use_case.repo.get_children.return_value = [
            WBSItem(id=str(uuid4()), code="2.1.1", name="First Child", level=3, project_id=project_id),
        ]

        request = CreateWBSItemRequest(
            project_id=project_id,
            name="Second Child",
            parent_id=parent_id
        )

        # Act
        result = use_case.execute(request)

        # Assert
        assert result.code == "2.1.2"
        assert result.level == 3

    def test_create_validates_max_depth(self, use_case):
        """GREEN: Reject creation beyond level 4"""
        # Arrange
        project_id = str(uuid4())
        parent_id = str(uuid4())

        use_case.repo.get_by_id.return_value = WBSItem(
            id=parent_id,
            code="1.1.1.1",
            name="Level 4",
            level=4,
            project_id=project_id
        )

        request = CreateWBSItemRequest(
            project_id=project_id,
            name="Level 5",
            parent_id=parent_id
        )

        # Act & Assert
        with pytest.raises(MaxDepthExceededError) as exc:
            use_case.execute(request)

        assert "maximum depth of 4" in str(exc.value)
        use_case.repo.save.assert_not_called()

class TestMoveWBSItemUseCase:
    """GREEN Phase: Make move tests pass"""

    @pytest.fixture
    def use_case(self):
        repo = Mock()
        return MoveWBSItemUseCase(repo)

    def test_move_updates_code_and_level(self, use_case):
        """GREEN: Move updates item hierarchy"""
        # Arrange
        item = WBSItem(
            id="item-1",
            code="2.1",
            name="Moving Item",
            level=2,
            project_id="proj-1"
        )
        new_parent = WBSItem(
            id="parent-2",
            code="3",
            name="New Parent",
            level=1,
            project_id="proj-1"
        )

        use_case.repo.get_by_id.side_effect = [item, new_parent]
        use_case.repo.get_children.return_value = []

        # Act
        result = use_case.execute(
            item_id="item-1",
            new_parent_id="parent-2"
        )

        # Assert
        assert result.code == "3.1"
        assert result.level == 2
        assert result.parent_id == "parent-2"

    def test_move_prevents_circular_reference(self, use_case):
        """GREEN: Cannot create cycles"""
        # Arrange
        parent = WBSItem(
            id="parent",
            code="1",
            name="Parent",
            level=1,
            project_id="proj-1"
        )
        child = WBSItem(
            id="child",
            code="1.1",
            name="Child",
            level=2,
            project_id="proj-1",
            parent_id="parent"
        )

        use_case.repo.get_by_id.side_effect = [parent, child]
        use_case.repo.is_ancestor.return_value = True

        # Act & Assert - Try to move parent under child
        with pytest.raises(CircularReferenceError):
            use_case.execute(
                item_id="parent",
                new_parent_id="child"
            )

    def test_move_updates_all_descendant_codes(self, use_case):
        """GREEN: Moving parent updates all children"""
        # Arrange
        parent = WBSItem(
            id="parent",
            code="2.1",
            name="Parent",
            level=2,
            project_id="proj-1"
        )
        child = WBSItem(
            id="child",
            code="2.1.1",
            name="Child",
            level=3,
            project_id="proj-1",
            parent_id="parent"
        )
        grandchild = WBSItem(
            id="grandchild",
            code="2.1.1.1",
            name="Grandchild",
            level=4,
            project_id="proj-1",
            parent_id="child"
        )

        new_parent = WBSItem(
            id="new-parent",
            code="3",
            name="New Parent",
            level=1,
            project_id="proj-1"
        )

        use_case.repo.get_by_id.side_effect = [parent, new_parent]
        use_case.repo.get_descendants.return_value = [child, grandchild]

        # Act
        result = use_case.execute(
            item_id="parent",
            new_parent_id="new-parent"
        )

        # Assert - All descendants updated
        assert result.code == "3.1"
        # Verify descendants were updated in repo
        calls = use_case.repo.update.call_args_list
        assert len(calls) == 3  # parent + 2 descendants

class TestDeleteWBSItemUseCase:
    """GREEN Phase: Make delete tests pass"""

    @pytest.fixture
    def use_case(self):
        repo = Mock()
        return DeleteWBSItemUseCase(repo)

    def test_delete_without_cascade_fails_if_has_children(self, use_case):
        """GREEN: Protect against accidental parent deletion"""
        # Arrange
        parent = WBSItem(
            id="parent",
            code="1",
            name="Parent",
            level=1,
            project_id="proj-1"
        )

        use_case.repo.get_by_id.return_value = parent
        use_case.repo.has_children.return_value = True

        # Act & Assert
        with pytest.raises(HasChildrenError) as exc:
            use_case.execute(item_id="parent", cascade=False)

        assert "children" in str(exc.value).lower()
        use_case.repo.delete.assert_not_called()

    def test_delete_with_cascade_removes_all_descendants(self, use_case):
        """GREEN: Cascade deletes entire subtree"""
        # Arrange
        parent = WBSItem(
            id="parent",
            code="1",
            name="Parent",
            level=1,
            project_id="proj-1"
        )
        descendants = [
            WBSItem(id="child", code="1.1", name="Child", level=2, project_id="proj-1"),
            WBSItem(id="grandchild", code="1.1.1", name="Grandchild", level=3, project_id="proj-1"),
        ]

        use_case.repo.get_by_id.return_value = parent
        use_case.repo.get_descendants.return_value = descendants

        # Act
        result = use_case.execute(item_id="parent", cascade=True)

        # Assert
        assert result.deleted_count == 3  # parent + 2 descendants

        # Verify all deleted in correct order (children first)
        calls = use_case.repo.delete.call_args_list
        assert calls[0][1]["item_id"] == "grandchild"
        assert calls[1][1]["item_id"] == "child"
        assert calls[2][1]["item_id"] == "parent"

    def test_delete_updates_parent_completion(self, use_case):
        """GREEN: Deleting child updates parent stats"""
        # Arrange
        child = WBSItem(
            id="child",
            code="1.1",
            name="Child",
            level=2,
            project_id="proj-1",
            parent_id="parent",
            completion=100
        )
        parent = WBSItem(
            id="parent",
            code="1",
            name="Parent",
            level=1,
            project_id="proj-1",
            completion=50
        )

        use_case.repo.get_by_id.return_value = child
        use_case.repo.get_parent.return_value = parent
        use_case.repo.has_children.return_value = False

        # Act
        use_case.execute(item_id="child", cascade=False)

        # Assert - Parent completion recalculated
        use_case.repo.update_parent_stats.assert_called_with("parent")
```

---

## 2.3 Mobile & Accessibility Tests

### File: `apps/web/tests/mobile/wbs-mobile.contract.test.tsx`

```typescript
/**
 * TS-MOB-WBS-001 - WBS Mobile Contract Tests
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { WBSTree } from '@/components/wbs/WBSTree';
import { mockWBSItems } from '@/tests/mocks/wbs';

describe('WBS Mobile Contracts - GREEN Phase', () => {
  it('should have touch targets minimum 44px', () => {
    render(<WBSTree items={mockWBSItems} />);

    const buttons = screen.getAllByRole('button');

    buttons.forEach(button => {
      const rect = button.getBoundingClientRect();

      expect(rect.height).toBeGreaterThanOrEqual(44);
      expect(rect.width).toBeGreaterThanOrEqual(44);

      // Visual verification
      expect(button).toHaveStyle({
        minHeight: '44px',
        minWidth: '44px'
      });
    });
  });

  it('should support swipe right to mark complete', () => {
    const onSwipeComplete = jest.fn();

    render(
      <WBSTree
        items={mockWBSItems}
        onSwipeComplete={onSwipeComplete}
      />
    );

    const item = screen.getByText('1 Preliminaries');

    // Simulate swipe right
    fireEvent.touchStart(item, {
      touches: [{ clientX: 0, clientY: 50 }]
    });
    fireEvent.touchMove(item, {
      touches: [{ clientX: 100, clientY: 50 }]
    });
    fireEvent.touchEnd(item);

    expect(onSwipeComplete).toHaveBeenCalledWith(
      expect.objectContaining({ code: '1' })
    );
  });

  it('should use bottom sheet for detail view on mobile', () => {
    const { container } = render(
      <WBSTree
        items={mockWBSItems}
        selectedItem={mockWBSItems[0]}
        isMobile={true}
      />
    );

    // Should render bottom sheet, not side panel
    expect(container.querySelector('.bottom-sheet')).toBeInTheDocument();
    expect(container.querySelector('.side-panel')).not.toBeInTheDocument();
  });

  it('should support pinch to zoom on Gantt', () => {
    const { container } = render(
      <ProcurementGantt plan={mockPlan} isMobile={true} />
    );

    const gantt = container.querySelector('.gantt-chart');

    // Simulate pinch
    fireEvent.touchStart(gantt, {
      touches: [
        { clientX: 100, clientY: 100 },
        { clientX: 200, clientY: 100 }
      ]
    });
    fireEvent.touchMove(gantt, {
      touches: [
        { clientX: 120, clientY: 100 },
        { clientX: 180, clientY: 100 }
      ]
    });
    fireEvent.touchEnd(gantt);

    // Should zoom in
    expect(gantt).toHaveStyle({ transform: expect.stringContaining('scale') });
  });

  it('should cache data for offline mode', async () => {
    // Setup offline
    Object.defineProperty(navigator, 'onLine', { value: false });

    const { result } = renderHook(() => useWbs('project-001'));

    // Should load from cache
    expect(result.current.items).toEqual(expect.any(Array));
    expect(result.current.isOffline).toBe(true);

    // Cleanup
    Object.defineProperty(navigator, 'onLine', { value: true });
  });

  it('should queue actions when offline', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false });

    const { result } = renderHook(() => useWbs('project-001'));

    // Attempt action while offline
    await result.current.updateItem({ id: '1', completion: 100 });

    // Should queue for sync
    expect(result.current.pendingActions).toHaveLength(1);
    expect(result.current.pendingActions[0].type).toBe('UPDATE_ITEM');

    // Cleanup
    Object.defineProperty(navigator, 'onLine', { value: true });
  });
});
```

### File: `apps/web/tests/accessibility/wbs-a11y.contract.test.tsx`

```typescript
/**
 * TS-A11Y-WBS-001 - WBS Accessibility Contract Tests
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe, toHaveNoViolations } from 'jest-axe';
import { WBSTree } from '@/components/wbs/WBSTree';
import { mockWBSItems } from '@/tests/mocks/wbs';

expect.extend(toHaveNoViolations);

describe('WBS Accessibility Contracts - GREEN Phase', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(<WBSTree items={mockWBSItems} />);

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have proper ARIA tree structure', () => {
    render(<WBSTree items={mockWBSItems} />);

    // Tree role
    const tree = screen.getByRole('tree');
    expect(tree).toHaveAttribute('aria-label', 'Work Breakdown Structure');

    // Treeitem roles
    const items = screen.getAllByRole('treeitem');
    expect(items.length).toBeGreaterThan(0);

    // Expanded state
    const expandedItems = screen.getAllByRole('treeitem', { expanded: true });
    expect(expandedItems).toHaveLength(expect.any(Number));
  });

  it('should support keyboard navigation', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();

    render(<WBSTree items={mockWBSItems} onSelect={onSelect} />);

    // Tab to first item
    await user.tab();
    expect(screen.getByText('1 Preliminaries')).toHaveFocus();

    // Arrow down
    await user.keyboard('{ArrowDown}');
    expect(screen.getByText('2 Substructure')).toHaveFocus();

    // Arrow right to expand
    await user.keyboard('{ArrowRight}');
    expect(screen.getByText('2.1 Foundation')).toBeInTheDocument();

    // Arrow left to collapse
    await user.keyboard('{ArrowLeft}');
    expect(screen.queryByText('2.1 Foundation')).not.toBeInTheDocument();

    // Enter to select
    await user.keyboard('{Enter}');
    expect(onSelect).toHaveBeenCalled();

    // Space to toggle expand
    await user.keyboard(' ');
    expect(screen.getByText('2.1 Foundation')).toBeInTheDocument();
  });

  it('should have sufficient color contrast', async () => {
    const { container } = render(
      <WBSTree items={mockWBSItemsWithAlerts} />
    );

    const results = await axe(container, {
      rules: {
        'color-contrast': { enabled: true }
      }
    });

    expect(results).toHaveNoViolations();
  });

  it('should announce state changes to screen readers', async () => {
    const { rerender } = render(<WBSTree items={mockWBSItems} />);

    // Expand an item
    rerender(<WBSTree items={mockWBSItems} expandedItems={['1']} />);

    // Should have aria-live region
    const liveRegion = screen.getByRole('status');
    expect(liveRegion).toHaveTextContent(/expanded/i);
  });

  it('should have accessible labels for all interactive elements', () => {
    render(<WBSTree items={mockWBSItems} />);

    // All buttons must have labels
    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      expect(button).toHaveAccessibleName();
    });

    // Expand/collapse buttons
    const expandButtons = screen.getAllByRole('button', { name: /expand|collapse/i });
    expect(expandButtons.length).toBeGreaterThan(0);
  });
});
```

---

## Week 2 GREEN Phase Checklist

### WBS Domain Tests

- [ ] Create WBS item with auto-generated code
- [ ] Create child item inherits parent code
- [ ] Validate maximum depth (level 4)
- [ ] Move item updates code and level
- [ ] Prevent circular references
- [ ] Delete with cascade removes descendants
- [ ] Delete without cascade fails if has children

### WBS Component Tests

- [ ] Filter by completion status
- [ ] Search by name/code/description
- [ ] Color-code by alert severity
- [ ] Keyboard navigation (Arrow keys, Tab, Enter)
- [ ] Touch targets minimum 44px
- [ ] Swipe gestures on mobile
- [ ] ARIA tree structure
- [ ] No accessibility violations

### WBS Use Case Tests

- [ ] Generate code for root item
- [ ] Generate code for child item
- [ ] Update item properties
- [ ] Move item with descendant updates
- [ ] Bulk operations (future)

### Total: 80+ Tests (All should PASS by end of Week 2)

**Expected State at End of Week 2:**

- ✅ All Week 1 contract tests PASSING
- ✅ All Week 2 WBS tests PASSING
- ✅ WBS module functional
- ✅ Mobile responsive
- ✅ Accessible (WCAG AA)
- ⏳ Ready for Procurement (Week 3)

---

**Next:** TDD_WEEK3_TESTS.md - Procurement Module Tests
