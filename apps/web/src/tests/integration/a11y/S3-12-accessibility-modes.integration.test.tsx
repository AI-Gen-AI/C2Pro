/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";

describe("S3-12 RED - accessibility modes integration", () => {
  it("[S3-12-RED-INT-05] reduced-motion and 200% zoom remain operable", async () => {
    const response = await fetch("/api/v1/a11y/modes?motion=reduced&zoom=200");
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ operable: true, readable: true });
  });
});
