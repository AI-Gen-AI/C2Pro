/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";

describe("S3-12 RED - axe critical integration", () => {
  it("[S3-12-RED-INT-01] reports zero critical violations on key shell", async () => {
    const response = await fetch("/api/v1/a11y/axe-scan?scope=core-shell");
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ criticalViolations: 0 });
  });
});
