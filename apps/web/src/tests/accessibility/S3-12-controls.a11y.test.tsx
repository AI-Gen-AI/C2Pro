/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { AccessibilityControlsHarness } from "@/src/tests/accessibility/harness/AccessibilityControlsHarness";

describe("S3-12 RED - controls", () => {
  it("[S3-12-RED-UNIT-03] ensures controls have accessible names and focus-visible marker", () => {
    render(<AccessibilityControlsHarness />);

    const approve = screen.getByRole("button", { name: /approve alert/i });
    approve.focus();

    expect(approve).toHaveAttribute("data-focus-visible", "true");
  });
});
