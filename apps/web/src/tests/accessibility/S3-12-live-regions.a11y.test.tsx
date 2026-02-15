/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { AccessibilityLiveRegionHarness } from "@/src/tests/accessibility/harness/AccessibilityLiveRegionHarness";

describe("S3-12 RED - live regions", () => {
  it("[S3-12-RED-UNIT-06] announces async status updates without duplicate spam", () => {
    render(<AccessibilityLiveRegionHarness />);

    fireEvent.click(screen.getByRole("button", { name: /start processing/i }));
    expect(screen.getByRole("status")).toHaveTextContent(/processing started/i);
    expect(screen.getByTestId("live-announcement-count")).toHaveTextContent("1");
  });
});
