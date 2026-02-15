/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";

describe("S3-12 RED - tablet layout integration", () => {
  it("[S3-12-RED-INT-03] tablet layouts avoid clipping/overlap at key breakpoints", async () => {
    const response = await fetch("/api/v1/responsive/tablet-layout?sizes=768x1024,820x1180");
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ clipped: 0, overlaps: 0 });
  });

  it("[S3-12-RED-INT-04] orientation change preserves active state", async () => {
    const response = await fetch("/api/v1/responsive/tablet-orientation-state");
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ preserved: true });
  });
});
