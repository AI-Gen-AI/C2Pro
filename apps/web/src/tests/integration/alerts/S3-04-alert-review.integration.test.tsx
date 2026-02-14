/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
import { describe, expect, it } from "vitest";

describe("S3-04 RED - alert review integration", () => {
  it("[S3-04-RED-INT-01] approve mutation updates status and audit fields", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/alerts/a-1/approve", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({ approverId: "reviewer_a" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      id: "a-1",
      status: "approved",
      reviewedBy: "reviewer_a",
    });
  });

  it("[S3-04-RED-INT-02] reject mutation stores reason and prevents conflicting approve", async () => {
    const rejectResponse = await fetch("/api/v1/projects/proj_demo_001/alerts/a-2/reject", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({ reason: "False positive" }),
    });

    expect(rejectResponse.status).toBe(200);
    expect(await rejectResponse.json()).toMatchObject({
      id: "a-2",
      status: "rejected",
      rejectionReason: "False positive",
    });

    const conflictingApprove = await fetch("/api/v1/projects/proj_demo_001/alerts/a-2/approve", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({ approverId: "reviewer_b" }),
    });

    expect(conflictingApprove.status).toBe(409);
  });

  it("[S3-04-RED-INT-03] create mutation inserts alert and list ordering stays deterministic", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/alerts", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        title: "Missing insurance certificate",
        severity: "critical",
        clauseId: "c-700",
      }),
    });

    expect(response.status).toBe(201);
    expect(await response.json()).toMatchObject({
      title: "Missing insurance certificate",
      severity: "critical",
      clauseId: "c-700",
      rank: 1,
    });
  });

  it("[S3-04-RED-INT-04] update/delete return deterministic UI-safe error payloads on stale records", async () => {
    const updateResponse = await fetch("/api/v1/projects/proj_demo_001/alerts/a-missing", {
      method: "PATCH",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({ title: "new title" }),
    });

    expect(updateResponse.status).toBe(404);
    expect(await updateResponse.json()).toMatchObject({
      code: "ALERT_NOT_FOUND",
      detail: "Alert not found",
    });

    const deleteResponse = await fetch("/api/v1/projects/proj_demo_001/alerts/a-concurrent", {
      method: "DELETE",
    });

    expect(deleteResponse.status).toBe(409);
    expect(await deleteResponse.json()).toMatchObject({
      code: "ALERT_CONFLICT",
      detail: "Alert changed since last read",
    });
  });

  it("[S3-04-RED-INT-05] server refresh does not clobber in-progress modal edits", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001/alerts/sync", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        localDraft: {
          alertId: "a-5",
          title: "Draft title pending save",
        },
      }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      preservedDraft: {
        alertId: "a-5",
        title: "Draft title pending save",
      },
    });
  });
});
