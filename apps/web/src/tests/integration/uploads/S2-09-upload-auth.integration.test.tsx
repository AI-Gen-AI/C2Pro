/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { describe, expect, it } from "vitest";

describe("S2-09 RED - upload auth and tenant boundaries", () => {
  it("[S2-09-RED-07] rejects upload start when auth context is missing", async () => {
    /** Roadmap: S2-09 */
    const response = await fetch("/api/v1/projects/proj_demo_001/uploads/start", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        fileName: "contract.pdf",
        fileSizeBytes: 4_000_000,
        mimeType: "application/pdf",
      }),
    });

    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({
      code: "UNAUTHORIZED",
      detail: "Authentication required for upload",
    });
  });

  it("[S2-09-RED-08] rejects cross-tenant upload attempt", async () => {
    /** Roadmap: S2-09 */
    const response = await fetch(
      "/api/v1/projects/proj_other_tenant/uploads/start",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-tenant-id": "tenant_a",
        },
        body: JSON.stringify({
          fileName: "budget.bc3",
          fileSizeBytes: 1_000_000,
          mimeType: "application/octet-stream",
          projectTenantId: "tenant_b",
        }),
      },
    );

    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({
      code: "FORBIDDEN",
      detail: "Cross-tenant upload denied",
    });
  });
});

