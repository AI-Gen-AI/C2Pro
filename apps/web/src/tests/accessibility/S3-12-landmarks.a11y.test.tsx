/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { AccessibilityLandmarksHarness } from "@/src/tests/accessibility/harness/AccessibilityLandmarksHarness";

describe("S3-12 RED - landmarks", () => {
  it("[S3-12-RED-UNIT-01] renders header/nav/main/footer landmarks on core shell", () => {
    render(<AccessibilityLandmarksHarness />);

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });
});
