/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { describe, expect, it } from "vitest";
import { moveHighlightCursor } from "@/src/components/features/evidence/highlight-navigation";

describe("S3-01 RED - highlight navigation", () => {
  it("[S3-01-RED-UNIT-05] advances and clamps highlight cursor safely", () => {
    const ids = ["h1", "h2", "h3"];

    expect(moveHighlightCursor(ids, null, "next")).toBe("h1");
    expect(moveHighlightCursor(ids, "h1", "next")).toBe("h2");
    expect(moveHighlightCursor(ids, "h3", "next")).toBe("h3");
    expect(moveHighlightCursor(ids, "h1", "prev")).toBe("h1");
  });
});
