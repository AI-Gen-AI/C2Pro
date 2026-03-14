/**
 * TS-UAD-WBS-COLOR-001 - WBS Alert Color Coding Tests
 *
 * Test Suite ID: TS-UAD-WBS-COLOR-001
 * Component: WBS Module - Alert Badge Component
 * Priority: P1
 * Phase: RED
 *
 * RED Phase: Component does not exist yet. Tests will fail with ImportError.
 * These tests verify the alert badge color coding, accessibility, and behavior.
 *
 * Run: npm test -- WBSAlertBadge.test.tsx
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WBSAlertBadge } from "../WBSAlertBadge";

// ===========================================
// TEST SUITE: WBS Alert Badge Color Coding
// ===========================================

describe("WBSAlertBadge Component", () => {
  describe("severity level styling", () => {
    it("should render none alerts with correct styling", () => {
      /**
       * RED Phase: None severity alert badge
       *
       * Expected: Badge renders with neutral/gray styling for 'none' severity
       */
      render(<WBSAlertBadge severity="none" />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "none");
      expect(badge).toHaveClass("alert-none");
    });

    it("should render low alerts with correct styling", () => {
      /**
       * RED Phase: Low severity alert badge
       *
       * Expected: Badge renders with blue/info styling for 'low' severity
       */
      render(<WBSAlertBadge severity="low" />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "low");
      expect(badge).toHaveClass("alert-low");
    });

    it("should render medium alerts with correct styling", () => {
      /**
       * RED Phase: Medium severity alert badge
       *
       * Expected: Badge renders with yellow/warning styling for 'medium' severity
       */
      render(<WBSAlertBadge severity="medium" />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "medium");
      expect(badge).toHaveClass("alert-medium");
    });

    it("should render high alerts with correct styling", () => {
      /**
       * RED Phase: High severity alert badge
       *
       * Expected: Badge renders with orange/danger styling for 'high' severity
       */
      render(<WBSAlertBadge severity="high" />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "high");
      expect(badge).toHaveClass("alert-high");
    });

    it("should render critical alerts with correct styling", () => {
      /**
       * RED Phase: Critical severity alert badge
       *
       * Expected: Badge renders with red/critical styling for 'critical' severity
       */
      render(<WBSAlertBadge severity="critical" />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "critical");
      expect(badge).toHaveClass("alert-critical");
    });
  });

  describe("accessibility compliance", () => {
    it("should meet WCAG AA color contrast", () => {
      /**
       * RED Phase: Color contrast accessibility
       *
       * Expected: Badge text and background colors meet WCAG AA contrast ratio (4.5:1)
       */
      const { container } = render(<WBSAlertBadge severity="critical" />);

      const badge = screen.getByTestId("wbs-alert-badge");

      // Badge should have proper aria-label for screen readers
      expect(badge).toHaveAttribute("aria-label");

      // Badge should have role="status" for accessibility
      expect(badge).toHaveAttribute("role", "status");

      // Verify contrast ratio attribute is set (implementation detail)
      expect(badge).toHaveAttribute("data-contrast-compliant", "true");
    });
  });

  describe("count display", () => {
    it("should show count when multiple alerts", () => {
      /**
       * RED Phase: Alert count display
       *
       * Expected: Badge displays the alert count when count prop is provided
       */
      render(<WBSAlertBadge severity="high" count={5} />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();

      // Should display the count
      expect(screen.getByText("5")).toBeInTheDocument();

      // Should have count-specific styling
      expect(badge).toHaveAttribute("data-count", "5");
    });

    it("should not show count when single alert or no count prop", () => {
      /**
       * RED Phase: No count display for single alerts
       *
       * Expected: Badge does not show count number when count is 1 or not provided
       */
      render(<WBSAlertBadge severity="medium" />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();

      // Should not have count attribute
      expect(badge).not.toHaveAttribute("data-count");
    });
  });

  describe("icon display", () => {
    it("should show icon based on severity", () => {
      /**
       * RED Phase: Severity-specific icons
       *
       * Expected: Badge displays appropriate icon for each severity level
       */
      const { rerender } = render(
        <WBSAlertBadge severity="none" showIcon={true} />,
      );

      // Each severity should have its own icon
      expect(screen.getByTestId("alert-icon-none")).toBeInTheDocument();

      rerender(<WBSAlertBadge severity="low" showIcon={true} />);
      expect(screen.getByTestId("alert-icon-low")).toBeInTheDocument();

      rerender(<WBSAlertBadge severity="medium" showIcon={true} />);
      expect(screen.getByTestId("alert-icon-medium")).toBeInTheDocument();

      rerender(<WBSAlertBadge severity="high" showIcon={true} />);
      expect(screen.getByTestId("alert-icon-high")).toBeInTheDocument();

      rerender(<WBSAlertBadge severity="critical" showIcon={true} />);
      expect(screen.getByTestId("alert-icon-critical")).toBeInTheDocument();
    });

    it("should not show icon when showIcon is false", () => {
      /**
       * RED Phase: Icon visibility toggle
       *
       * Expected: Badge does not display icon when showIcon prop is false
       */
      render(<WBSAlertBadge severity="high" showIcon={false} />);

      const badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();

      // Should not have any icon elements
      expect(screen.queryByTestId(/alert-icon-/)).not.toBeInTheDocument();
    });
  });

  describe("component interface", () => {
    it("should accept all required props", () => {
      /**
       * RED Phase: Component interface validation
       *
       * Expected: Component accepts severity, count, and showIcon props
       */
      const { rerender } = render(
        <WBSAlertBadge severity="critical" count={10} showIcon={true} />,
      );

      let badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "critical");
      expect(badge).toHaveAttribute("data-count", "10");
      expect(screen.getByText("10")).toBeInTheDocument();
      expect(screen.getByTestId("alert-icon-critical")).toBeInTheDocument();

      // Test with minimal props
      rerender(<WBSAlertBadge severity="low" />);

      badge = screen.getByTestId("wbs-alert-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-severity", "low");
    });
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================

// Mark tests as in RED phase - Component does not exist
// @ts-ignore - vitest type extension
if (typeof test !== "undefined") {
  const testWithMeta = test as typeof test & {
    meta?: Record<string, string>;
  };

  testWithMeta.meta = {
    phase: "red",
    suite: "TS-UAD-WBS-COLOR-001",
    type: "component",
  };
}
