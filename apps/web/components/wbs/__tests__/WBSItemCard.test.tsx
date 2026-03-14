/**
 * TS-UAD-WBS-CARD-001 - WBS Item Card Component Tests
 *
 * Test Suite ID: TS-UAD-WBS-CARD-001
 * Component: WBS Module - Item Card Component
 * Priority: P1
 * Phase: GREEN (All tests passing)
 *
 * Contract tests verify WBSItemCard component prop interface and behavior.
 * GREEN Phase: All 12 tests passing - Implementation complete.
 *
 * Run: npm test -- WBSItemCard.test.tsx
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WBSItemCard } from "../WBSItemCard";

// ===========================================
// FIXTURES
// ===========================================

const mockWBSItem = {
  id: "1.1",
  code: "1.1",
  name: "Planning Phase",
  level: 2,
  completion: 75,
  budget: {
    amount: 450000,
    currency: "EUR",
  },
  startDate: "2025-05-01",
  endDate: "2025-05-15",
  alerts: [],
};

const mockItemWithAlert = {
  ...mockWBSItem,
  id: "1.2",
  code: "1.2",
  name: "Execution Phase",
  completion: 25,
  alerts: [
    {
      id: "alert-1",
      severity: "high",
      message: "Budget overrun detected",
    },
  ],
};

// ===========================================
// CONTRACT TESTS
// ===========================================

describe("WBSItemCard Component Contract", () => {
  describe("basic rendering", () => {
    it("should render item name and code [TEST-01]", () => {
      /**
       * GREEN Phase: Basic item information display
       *
       * Expected: Shows WBS code and name
       */
      render(<WBSItemCard item={mockWBSItem} />);

      // Should display code
      expect(screen.getByText("1.1")).toBeInTheDocument();

      // Should display name
      expect(screen.getByText("Planning Phase")).toBeInTheDocument();
    });

    it("should render completion percentage [TEST-02]", () => {
      /**
       * RED Phase: Progress indicator
       *
       * Expected: Shows completion percentage (75%)
       */
      render(<WBSItemCard item={mockWBSItem} />);

      // Should show percentage
      expect(screen.getByText("75%")).toBeInTheDocument();

      // Should have progress indicator (aria-progressbar or visual bar)
      const progressBar = screen.getByRole("progressbar");
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute("aria-valuenow", "75");
    });

    it("should render budget information when available [TEST-03]", () => {
      /**
       * RED Phase: Budget display
       *
       * Expected: Shows formatted budget amount
       */
      render(<WBSItemCard item={mockWBSItem} />);

      // Should display formatted budget
      expect(screen.getByText(/€450,000/)).toBeInTheDocument();
    });

    it("should not show budget section when no budget [TEST-04]", () => {
      /**
       * RED Phase: Conditional budget display
       *
       * Expected: No budget elements when budget is null
       */
      const itemWithoutBudget = { ...mockWBSItem, budget: null };
      render(<WBSItemCard item={itemWithoutBudget} />);

      // Should not have budget-related elements
      expect(screen.queryByText(/€/)).not.toBeInTheDocument();
    });
  });

  describe("alert indicators", () => {
    it("should render alert badge when item has alerts [TEST-05]", () => {
      /**
       * RED Phase: Alert indicator display
       *
       * Expected: Shows alert badge with severity styling
       */
      render(<WBSItemCard item={mockItemWithAlert} />);

      // Should show alert indicator
      const alertBadge = screen.getByTestId("alert-badge");
      expect(alertBadge).toBeInTheDocument();

      // Should indicate severity
      expect(alertBadge).toHaveAttribute("data-severity", "high");
    });

    it("should not show alert badge when no alerts [TEST-06]", () => {
      /**
       * RED Phase: No alerts state
       *
       * Expected: No alert badge when item.alerts is empty
       */
      render(<WBSItemCard item={mockWBSItem} />);

      // Should not have alert badge
      expect(screen.queryByTestId("alert-badge")).not.toBeInTheDocument();
    });
  });

  describe("interaction handling", () => {
    it("should call onClick handler when card is clicked [TEST-07]", () => {
      /**
       * RED Phase: Click interaction
       *
       * Expected: onClick callback invoked with item data
       */
      const handleClick = vi.fn();
      render(<WBSItemCard item={mockWBSItem} onClick={handleClick} />);

      // Click the card
      const card = screen.getByTestId("wbs-item-card");
      fireEvent.click(card);

      // Should call handler with item
      expect(handleClick).toHaveBeenCalledTimes(1);
      expect(handleClick).toHaveBeenCalledWith(mockWBSItem);
    });

    it("should render action buttons [TEST-08]", () => {
      /**
       * RED Phase: Action buttons display
       *
       * Expected: Edit and delete buttons visible
       */
      render(<WBSItemCard item={mockWBSItem} />);

      // Should have edit button
      expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();

      // Should have delete button
      expect(
        screen.getByRole("button", { name: /delete/i }),
      ).toBeInTheDocument();
    });

    it("should call onEdit when edit button clicked [TEST-09]", () => {
      /**
       * RED Phase: Edit action
       *
       * Expected: onEdit callback invoked
       */
      const handleEdit = vi.fn();
      render(<WBSItemCard item={mockWBSItem} onEdit={handleEdit} />);

      // Click edit button
      const editButton = screen.getByRole("button", { name: /edit/i });
      fireEvent.click(editButton);

      // Should call onEdit with item
      expect(handleEdit).toHaveBeenCalledTimes(1);
      expect(handleEdit).toHaveBeenCalledWith(mockWBSItem);
    });

    it("should call onDelete when delete button clicked [TEST-10]", () => {
      /**
       * RED Phase: Delete action
       *
       * Expected: onDelete callback invoked
       */
      const handleDelete = vi.fn();
      render(<WBSItemCard item={mockWBSItem} onDelete={handleDelete} />);

      // Click delete button
      const deleteButton = screen.getByRole("button", { name: /delete/i });
      fireEvent.click(deleteButton);

      // Should call onDelete with item
      expect(handleDelete).toHaveBeenCalledTimes(1);
      expect(handleDelete).toHaveBeenCalledWith(mockWBSItem);
    });
  });

  describe("state handling", () => {
    it("should show selected state when selected prop is true [TEST-11]", () => {
      /**
       * RED Phase: Selected state styling
       *
       * Expected: Visual indication of selection (border, background)
       */
      render(<WBSItemCard item={mockWBSItem} selected={true} />);

      const card = screen.getByTestId("wbs-item-card");
      expect(card).toHaveAttribute("data-selected", "true");
      // Or check for selected CSS class
      expect(
        card.classList.contains("selected") ||
          card.getAttribute("aria-selected"),
      ).toBeTruthy();
    });

    it("should not be selectable when disabled prop is true [TEST-12]", () => {
      /**
       * RED Phase: Disabled state
       *
       * Expected: No click handler called, grayed out appearance
       */
      const handleClick = vi.fn();
      render(
        <WBSItemCard
          item={mockWBSItem}
          onClick={handleClick}
          disabled={true}
        />,
      );

      // Click should not trigger handler
      const card = screen.getByTestId("wbs-item-card");
      fireEvent.click(card);
      expect(handleClick).not.toHaveBeenCalled();

      // Should have disabled styling
      expect(card).toHaveAttribute("aria-disabled", "true");
    });
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================

// Mark tests as contract tests in GREEN phase
// All tests passing - Implementation complete
// @ts-ignore - vitest type extension
if (typeof test !== "undefined") {
  const testWithMeta = test as typeof test & {
    meta?: Record<string, string>;
  };

  testWithMeta.meta = {
    phase: "green",
    suite: "TS-UAD-WBS-CARD-001",
    type: "contract",
  };
}
