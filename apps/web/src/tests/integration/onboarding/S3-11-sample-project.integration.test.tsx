/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */
import { describe, expect, it } from "vitest";

describe("S3-11 RED - onboarding sample project integration", () => {
  it("[S3-11-RED-INT-01] start CTA provisions sample project and routes to workspace", async () => {
    const response = await fetch("/api/v1/onboarding/sample-project/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ userId: "user_demo" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      projectId: "proj_sample_001",
      route: "/dashboard/projects/proj_sample_001",
    });
  });

  it("[S3-11-RED-INT-02] existing sample project is reused idempotently", async () => {
    const response = await fetch("/api/v1/onboarding/sample-project/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ userId: "user_demo" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      reused: true,
      duplicateCreated: false,
    });
  });

  it("[S3-11-RED-INT-03] ready workspace hydrates core widgets for time-to-value", async () => {
    const response = await fetch("/api/v1/onboarding/sample-project/ready?projectId=proj_sample_001");

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      widgets: {
        documents: "ready",
        alerts: "ready",
        stakeholders: "ready",
      },
    });
  });

  it("[S3-11-RED-INT-04] failure/retry recovers while preserving onboarding context", async () => {
    const response = await fetch("/api/v1/onboarding/sample-project/retry", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sessionId: "onb_001" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      sessionId: "onb_001",
      state: "ready",
      recovered: true,
    });
  });

  it("[S3-11-RED-INT-05] emits time-to-value telemetry sequence", async () => {
    const response = await fetch("/api/v1/onboarding/sample-project/telemetry?sessionId=onb_001");

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      events: ["start", "ready"],
      elapsedMs: expect.any(Number),
    });
  });
});
