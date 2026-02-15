/**
 * Test Suite ID: S3-08
 * Roadmap Reference: S3-08 Legal disclaimer modal (Gate 8)
 */
import { describe, expect, it } from "vitest";

describe("S3-08 RED - legal disclaimer integration", () => {
  it("[S3-08-RED-INT-01] fetches acceptance status and shows modal when not accepted", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/status", {
      method: "GET",
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      accepted: false,
      version: "v1.0",
      mustPrompt: true,
    });
  });

  it("[S3-08-RED-INT-02] confirm acceptance persists and unblocks gate", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/accept", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ version: "v1.0" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      accepted: true,
      gateBlocked: false,
    });
  });

  it("[S3-08-RED-INT-03] accepted version survives remount and skips re-prompt", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/status", {
      method: "GET",
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      accepted: true,
      version: "v1.0",
      mustPrompt: false,
    });
  });

  it("[S3-08-RED-INT-04] backend failure keeps gate blocked with deterministic error", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/accept", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ version: "v1.0", forceError: true }),
    });

    expect(response.status).toBe(500);
    expect(await response.json()).toMatchObject({
      code: "DISCLAIMER_PERSIST_FAILED",
      gateBlocked: true,
    });
  });

  it("[S3-08-RED-INT-05] acceptance is tenant/user/version scoped", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/status", {
      method: "GET",
      headers: {
        "x-tenant-id": "tenant_alt",
        "x-user-id": "user_alt",
      },
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      accepted: false,
      mustPrompt: true,
      scope: "tenant_alt:user_alt:v1.0",
    });
  });
});
