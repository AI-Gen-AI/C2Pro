/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { describe, expect, it } from "vitest";
import { resolveHighlightStyle } from "@/components/features/evidence/highlight-style";

describe("S3-01 RED - highlight style", () => {
  it("[S3-01-RED-UNIT-04] encodes selected/approved/rejected visual states", () => {
    const selected = resolveHighlightStyle({
      severity: "critical",
      validationStatus: "pending",
      isActive: true,
    });
    const approved = resolveHighlightStyle({
      severity: "medium",
      validationStatus: "approved",
      isActive: false,
    });
    const rejected = resolveHighlightStyle({
      severity: "low",
      validationStatus: "rejected",
      isActive: false,
    });

    expect(selected.className).toContain("ring");
    expect(approved.className).toContain("approved");
    expect(rejected.className).toContain("rejected");
  });
});
