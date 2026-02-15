/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */
import { describe, expect, it, vi } from "vitest";
import {
  createDoubleInvalidator,
} from "@/src/lib/query/double-invalidation";

describe("S3-06 RED - double invalidation", () => {
  it("[S3-06-RED-UNIT-03] invalidates alerts and coherence keys in one call", async () => {
    const invalidate = vi.fn().mockResolvedValue(undefined);
    const invalidator = createDoubleInvalidator({ invalidate });

    await invalidator.invalidateForAlertMutation("proj_demo_001");

    expect(invalidate).toHaveBeenCalledWith(["alerts", "proj_demo_001"]);
    expect(invalidate).toHaveBeenCalledWith(["coherence", "proj_demo_001"]);
    expect(invalidate).toHaveBeenCalledTimes(2);
  });

  it("[S3-06-RED-UNIT-04] dedupes repeated invalidation while one cycle is inflight", async () => {
    const invalidate = vi
      .fn()
      .mockResolvedValue(undefined);

    const invalidator = createDoubleInvalidator({ invalidate });

    await Promise.all([
      invalidator.invalidateForAlertMutation("proj_demo_001"),
      invalidator.invalidateForAlertMutation("proj_demo_001"),
    ]);

    expect(invalidate).toHaveBeenCalledTimes(2);
  });
});
