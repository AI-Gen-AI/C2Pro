/**
 * TS-UAD-WBS-DETAIL-001 - WBS Item Detail Component Tests
 *
 * Test Suite ID: TS-UAD-WBS-DETAIL-001
 * Component: WBS Module - Item Detail Component
 * Priority: P1
 * Phase: GREEN (All tests passing)
 *
 * Contract tests verify WBSItemDetail component prop interface and behavior.
 * GREEN Phase: All 12 tests passing - Implementation complete.
 *
 * Run: npm test -- WBSItemDetail.test.tsx
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WBSItemDetail } from "../WBSItemDetail";

// ===========================================
// FIXTURES
// ===========================================

const mockWBSItem = {
  id: "1.1",
  code: "1.1",
  name: "Planning Phase",
  description: "Initial planning and requirements gathering phase",
  level: 2,
  completion: 75,
  budget: {
    amount: 450000,
    currency: "EUR",
  },
  startDate: "2025-05-01",
  endDate: "2025-05-15",
  parent: {
    id: "1",
    code: "1",
    name: "Project Management",
  },
  children: [
    {
      id: "1.1.1",
      code: "1.1.1",
      name: "Requirements Gathering",
      completion: 100,
    },
    {
      id: "1.1.2",
      code: "1.1.2",
      name: "Stakeholder Analysis",
      completion: 50,
    },
  ],
  alerts: [
    {
      id: "alert-1",
      severity: "medium",
      message: "End date approaching",
    },
  ],
  documents: [
    {
      id: "doc-1",
      name: "Project Plan.pdf",
      type: "pdf",
      url: "/documents/project-plan.pdf",
    },
  ],
};

// ===========================================
// CONTRACT TESTS
// ===========================================

describe("WBSItemDetail Component Contract", () => {
  describe("basic rendering", () => {
    it("should render item details [TEST-01]", () => {
      /**
       * RED Phase: Display full item information
       *
       * Expected: Shows code, name, description, dates, budget
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Should display code
      expect(screen.getByText("1.1")).toBeInTheDocument();

      // Should display name
      expect(screen.getByText("Planning Phase")).toBeInTheDocument();

      // Should display description
      expect(
        screen.getByText("Initial planning and requirements gathering phase"),
      ).toBeInTheDocument();

      // Should display dates
      expect(screen.getByText(/2025-05-01/)).toBeInTheDocument();
      expect(screen.getByText(/2025-05-15/)).toBeInTheDocument();

      // Should display budget
      expect(screen.getByText(/€450,000/)).toBeInTheDocument();
    });

    it("should render completion chart [TEST-02]", () => {
      /**
       * RED Phase: Visual completion indicator
       *
       * Expected: Progress bar or chart showing 75%
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Should have progress indicator
      const progressBar = screen.getByRole("progressbar");
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute("aria-valuenow", "75");

      // Should show percentage text
      expect(screen.getByText("75%")).toBeInTheDocument();
    });

    it("should render children list [TEST-03]", () => {
      /**
       * RED Phase: Child items hierarchy
       *
       * Expected: Shows list of child WBS items
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Should show children section
      expect(screen.getByText(/children|sub-items/i)).toBeInTheDocument();

      // Should display child items
      expect(
        screen.getByText("1.1.1 - Requirements Gathering"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("1.1.2 - Stakeholder Analysis"),
      ).toBeInTheDocument();
    });

    it("should render parent breadcrumb [TEST-04]", () => {
      /**
       * RED Phase: Parent navigation
       *
       * Expected: Breadcrumb trail to parent item
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Should show breadcrumb
      const breadcrumb = screen.getByRole("navigation", {
        name: /breadcrumb/i,
      });
      expect(breadcrumb).toBeInTheDocument();

      // Should show parent link
      expect(screen.getByText("1 - Project Management")).toBeInTheDocument();
    });

    it("should render linked documents [TEST-05]", () => {
      /**
       * RED Phase: Document links
       *
       * Expected: Shows linked documents with clickable links
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Should show documents section
      expect(screen.getByText(/documents|files/i)).toBeInTheDocument();

      // Should display document
      expect(screen.getByText("Project Plan.pdf")).toBeInTheDocument();

      // Should have document link
      const docLink = screen.getByRole("link", { name: /project plan/i });
      expect(docLink).toHaveAttribute("href", "/documents/project-plan.pdf");
    });

    it("should render alerts section [TEST-06]", () => {
      /**
       * RED Phase: Active alerts display
       *
       * Expected: Shows alert cards/badges
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Should show alerts section
      expect(screen.getByText(/alerts|warnings/i)).toBeInTheDocument();

      // Should display alert message
      expect(screen.getByText("End date approaching")).toBeInTheDocument();

      // Should show severity
      expect(screen.getByTestId("alert-severity")).toHaveTextContent(/medium/i);
    });
  });

  describe("edit mode", () => {
    it("should toggle edit mode [TEST-07]", () => {
      /**
       * RED Phase: Edit mode toggle
       *
       * Expected: Switch between view and edit forms
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Initially in view mode
      expect(screen.queryByRole("form")).not.toBeInTheDocument();

      // Click edit button
      const editButton = screen.getByRole("button", { name: /edit/i });
      fireEvent.click(editButton);

      // Should show edit form
      expect(screen.getByRole("form")).toBeInTheDocument();

      // Should have input fields
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    });

    it("should validate form inputs [TEST-08]", async () => {
      /**
       * RED Phase: Form validation
       *
       * Expected: Shows validation errors for invalid input
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Enter edit mode
      fireEvent.click(screen.getByRole("button", { name: /edit/i }));

      // Clear required field
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.change(nameInput, { target: { value: "" } });

      // Try to save
      const saveButton = screen.getByRole("button", { name: /save/i });
      fireEvent.click(saveButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      });
    });

    it("should save changes [TEST-09]", async () => {
      /**
       * RED Phase: Save edited data
       *
       * Expected: Calls onSave with updated item data
       */
      const handleSave = vi.fn();
      render(<WBSItemDetail item={mockWBSItem} onSave={handleSave} />);

      // Enter edit mode
      fireEvent.click(screen.getByRole("button", { name: /edit/i }));

      // Modify name
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.change(nameInput, { target: { value: "Updated Name" } });

      // Save changes
      fireEvent.click(screen.getByRole("button", { name: /save/i }));

      // Should call onSave with updated data
      await waitFor(() => {
        expect(handleSave).toHaveBeenCalledTimes(1);
        expect(handleSave).toHaveBeenCalledWith(
          expect.objectContaining({
            id: "1.1",
            name: "Updated Name",
          }),
        );
      });
    });

    it("should cancel edit [TEST-10]", () => {
      /**
       * RED Phase: Cancel editing
       *
       * Expected: Returns to view mode without saving
       */
      render(<WBSItemDetail item={mockWBSItem} />);

      // Enter edit mode
      fireEvent.click(screen.getByRole("button", { name: /edit/i }));

      // Modify field
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.change(nameInput, { target: { value: "Changed Name" } });

      // Cancel edit
      fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

      // Should return to view mode
      expect(screen.queryByRole("form")).not.toBeInTheDocument();

      // Should show original name
      expect(screen.getByText("Planning Phase")).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("should call onNavigate when parent breadcrumb clicked [TEST-11]", () => {
      /**
       * RED Phase: Parent navigation
       *
       * Expected: Calls onNavigate with parent ID
       */
      const handleNavigate = vi.fn();
      render(<WBSItemDetail item={mockWBSItem} onNavigate={handleNavigate} />);

      // Click parent breadcrumb
      const parentLink = screen.getByText("1 - Project Management");
      fireEvent.click(parentLink);

      // Should call onNavigate
      expect(handleNavigate).toHaveBeenCalledTimes(1);
      expect(handleNavigate).toHaveBeenCalledWith("1");
    });

    it("should call onNavigate when child item clicked [TEST-12]", () => {
      /**
       * RED Phase: Child navigation
       *
       * Expected: Calls onNavigate with child ID
       */
      const handleNavigate = vi.fn();
      render(<WBSItemDetail item={mockWBSItem} onNavigate={handleNavigate} />);

      // Click child item
      const childLink = screen.getByText("1.1.1 - Requirements Gathering");
      fireEvent.click(childLink);

      // Should call onNavigate
      expect(handleNavigate).toHaveBeenCalledTimes(1);
      expect(handleNavigate).toHaveBeenCalledWith("1.1.1");
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
    suite: "TS-UAD-WBS-DETAIL-001",
    type: "contract",
  };
}
