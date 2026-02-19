/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */
import { describe, expect, it } from "vitest";
import { createWatermarkToken } from "@/components/features/evidence/watermark-token";

describe("S3-03 RED - watermark token", () => {
  it("[S3-03-RED-UNIT-01] returns deterministic pseudonym token for same seed", () => {
    const first = createWatermarkToken({
      tenantId: "tenant-alpha",
      userSeed: "user-seed-001",
      sessionNonce: "session-123",
    });
    const second = createWatermarkToken({
      tenantId: "tenant-alpha",
      userSeed: "user-seed-001",
      sessionNonce: "session-123",
    });

    expect(first).toEqual(second);
    expect(first).toMatch(/^[A-Z0-9-]{8,32}$/);
  });

  it("[S3-03-RED-UNIT-02] changes token when seed changes and never echoes raw ID", () => {
    const baseline = createWatermarkToken({
      tenantId: "tenant-alpha",
      userSeed: "user-seed-001",
      sessionNonce: "session-123",
    });

    const rotated = createWatermarkToken({
      tenantId: "tenant-alpha",
      userSeed: "user-seed-999",
      sessionNonce: "session-123",
    });

    expect(rotated).not.toEqual(baseline);
    expect(rotated).not.toContain("user-seed-999");
  });
});
