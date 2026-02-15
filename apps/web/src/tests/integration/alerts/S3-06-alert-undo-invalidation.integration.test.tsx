/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */
import { describe, expect, it } from "vitest";

describe("S3-06 RED - alert undo + invalidation integration", () => {
  it("[S3-06-RED-INT-01] approve/reject mutation triggers double invalidation + fresh coherence snapshot", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/alerts/a-1/approve", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ approverId: "reviewer_a" }),
    });

    expect(response.status).toBe(200);

    const coherence = await fetch("/api/v1/projects/proj_demo_001/coherence/summary");
    expect(coherence.status).toBe(200);
    expect(await coherence.json()).toMatchObject({ freshness: "fresh" });
  });

  it("[S3-06-RED-INT-02] undo after mutation restores alert state and coherence counters", async () => {
    const undoResponse = await fetch("/api/v1/projects/proj_demo_001/alerts/a-1/undo", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ targetStatus: "pending" }),
    });

    expect(undoResponse.status).toBe(200);
    expect(await undoResponse.json()).toMatchObject({
      id: "a-1",
      status: "pending",
      coherenceDelta: -1,
    });
  });

  it("[S3-06-RED-INT-03] sequential mutation+undo avoids stale mixed list/coherence state", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/alerts/coherence-sync", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        operations: ["approve:a-1", "reject:a-2", "undo:a-2"],
      }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      alertsConsistent: true,
      coherenceConsistent: true,
    });
  });

  it("[S3-06-RED-INT-04] undo failure path keeps state deterministic and surfaces explicit error", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/alerts/a-stale/undo", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ targetStatus: "pending" }),
    });

    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({
      code: "UNDO_CONFLICT",
      detail: "Undo could not be applied",
    });
  });
});
