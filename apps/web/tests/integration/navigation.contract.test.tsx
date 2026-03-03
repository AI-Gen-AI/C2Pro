/**
 * TS-INT-NAV-001 - Cross-Module Navigation Contract Tests
 *
 * Test Suite ID: TS-INT-NAV-001
 * Type: Integration Tests
 * Priority: P1
 * Phase: RED (Write failing tests first)
 *
 * Tests cross-module navigation between WBS, Procurement, Alerts, and Coherence modules.
 * These tests will FAIL until navigation components are implemented.
 *
 * Run: npm test -- navigation.contract.test.tsx
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CrossModuleNavigator } from "../../components/navigation/CrossModuleNavigator";
import { WBSDetailWithLinks } from "../../components/wbs/WBSDetailWithLinks";
import { AlertDetailWithLinks } from "../../components/alerts/AlertDetailWithLinks";
import { GlobalSearch } from "../../components/search/GlobalSearch";

// ===========================================
// FIXTURES
// ===========================================

const mockWBSItemWithProcurement = {
  id: "1.1",
  code: "1.1",
  name: "Construction Materials",
  procurementItems: [
    {
      id: "proc-1",
      title: "Steel Beams Supply",
      status: "in-progress",
      value: 150000,
    },
    {
      id: "proc-2",
      title: "Concrete Delivery",
      status: "pending",
      value: 75000,
    },
  ],
};

const mockAlertWithEntities = {
  id: "alert-1",
  severity: "high",
  message: "Budget overrun in WBS 1.1",
  affectedEntities: [
    {
      type: "wbs",
      id: "1.1",
      name: "Construction Materials",
    },
    {
      type: "procurement",
      id: "proc-1",
      name: "Steel Beams Supply",
    },
  ],
};

const mockCoherenceCategory = {
  category: "BUDGET",
  score: 85,
  issues: 3,
};

const mockSearchResults = [
  {
    type: "wbs",
    id: "1.1",
    title: "Construction Materials",
    module: "WBS",
  },
  {
    type: "procurement",
    id: "proc-1",
    title: "Steel Beams Supply",
    module: "Procurement",
  },
  {
    type: "document",
    id: "doc-1",
    title: "Project Specs.pdf",
    module: "Documents",
  },
];

// ===========================================
// CONTRACT TESTS
// ===========================================

describe("TS-INT-NAV-001: Cross-Module Navigation", () => {
  describe("WBS-Procurement Integration", () => {
    it("should display linked procurement items in WBS detail [TEST-01]", () => {
      /**
       * RED Phase: WBS-Procurement linking
       *
       * Expected: WBS detail shows linked procurement items
       */
      render(<WBSDetailWithLinks item={mockWBSItemWithProcurement} />);

      // Should show procurement section
      expect(screen.getByText(/procurement|purchasing/i)).toBeInTheDocument();

      // Should display linked items
      expect(screen.getByText("Steel Beams Supply")).toBeInTheDocument();
      expect(screen.getByText("Concrete Delivery")).toBeInTheDocument();

      // Should show procurement details
      expect(screen.getByText(/€150,000/)).toBeInTheDocument();
      expect(screen.getByText(/in-progress/i)).toBeInTheDocument();
    });

    it("should navigate to procurement tab when procurement link clicked [TEST-02]", async () => {
      /**
       * RED Phase: Navigation to procurement module
       *
       * Expected: Clicking procurement link calls onNavigate with procurement ID
       */
      const handleNavigate = vi.fn();
      render(
        <WBSDetailWithLinks
          item={mockWBSItemWithProcurement}
          onNavigate={handleNavigate}
        />,
      );

      // Find and click procurement link
      const procurementLink = screen.getByText("Steel Beams Supply");
      fireEvent.click(procurementLink);

      // Should call onNavigate with procurement ID
      await waitFor(() => {
        expect(handleNavigate).toHaveBeenCalledWith("procurement", "proc-1");
      });
    });
  });

  describe("Alert-Entity Integration", () => {
    it("should display affected entities in alert detail [TEST-03]", () => {
      /**
       * RED Phase: Alert-entity linking
       *
       * Expected: Alert detail shows affected WBS and Procurement items
       */
      render(<AlertDetailWithLinks alert={mockAlertWithEntities} />);

      // Should show affected entities section
      expect(screen.getByText(/affected|related|linked/i)).toBeInTheDocument();

      // Should display WBS item
      expect(screen.getByText("Construction Materials")).toBeInTheDocument();
      expect(screen.getByText(/wbs/i)).toBeInTheDocument();

      // Should display procurement item
      expect(screen.getByText("Steel Beams Supply")).toBeInTheDocument();
      expect(screen.getByText(/procurement/i)).toBeInTheDocument();
    });

    it("should navigate to entity when clicked in alert detail [TEST-04]", async () => {
      /**
       * RED Phase: Navigation from alerts
       *
       * Expected: Clicking entity link calls onNavigate with entity type and ID
       */
      const handleNavigate = vi.fn();
      render(
        <AlertDetailWithLinks
          alert={mockAlertWithEntities}
          onNavigate={handleNavigate}
        />,
      );

      // Click WBS entity link
      const wbsLink = screen.getByText("Construction Materials");
      fireEvent.click(wbsLink);

      // Should call onNavigate with type and ID
      await waitFor(() => {
        expect(handleNavigate).toHaveBeenCalledWith("wbs", "1.1");
      });
    });
  });

  describe("Coherence Score Navigation", () => {
    it("should navigate to category detail when coherence score clicked [TEST-05]", async () => {
      /**
       * RED Phase: Coherence score navigation
       *
       * Expected: Clicking coherence score calls onNavigate with category
       */
      const handleNavigate = vi.fn();
      render(
        <CrossModuleNavigator
          coherenceData={mockCoherenceCategory}
          onNavigate={handleNavigate}
        />,
      );

      // Find coherence score
      const coherenceScore = screen.getByText(/85/);
      expect(coherenceScore).toBeInTheDocument();

      // Click the score
      fireEvent.click(coherenceScore);

      // Should call onNavigate with coherence category
      await waitFor(() => {
        expect(handleNavigate).toHaveBeenCalledWith("coherence", "BUDGET");
      });
    });
  });

  describe("Global Search", () => {
    it("should search across all modules [TEST-06]", async () => {
      /**
       * RED Phase: Global search integration
       *
       * Expected: Search returns results from WBS, Procurement, Documents, etc.
       */
      const handleSearch = vi.fn().mockResolvedValue(mockSearchResults);
      const handleSelect = vi.fn();

      render(
        <GlobalSearch
          onSearch={handleSearch}
          onSelect={handleSelect}
          results={mockSearchResults}
        />,
      );

      // Type search query
      const searchInput = screen.getByPlaceholderText(/search/i);
      fireEvent.change(searchInput, { target: { value: "steel" } });

      // Submit search
      fireEvent.submit(searchInput);

      // Should call search handler
      await waitFor(() => {
        expect(handleSearch).toHaveBeenCalledWith("steel");
      });

      // Should show results from different modules
      expect(screen.getByText("Construction Materials")).toBeInTheDocument();
      expect(screen.getByText("WBS")).toBeInTheDocument();

      expect(screen.getByText("Steel Beams Supply")).toBeInTheDocument();
      expect(screen.getByText("Procurement")).toBeInTheDocument();

      expect(screen.getByText("Project Specs.pdf")).toBeInTheDocument();
      expect(screen.getByText("Documents")).toBeInTheDocument();
    });
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================

// Mark tests as integration tests in RED phase
// @ts-ignore - vitest type extension
if (typeof test !== "undefined") {
  test.meta = {
    phase: "red",
    suite: "TS-INT-NAV-001",
    type: "integration",
  };
}
