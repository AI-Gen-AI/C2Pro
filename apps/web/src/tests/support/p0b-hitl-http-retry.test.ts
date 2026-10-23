import { describe, expect, it } from "vitest";
import { approveWithHttpResponse, type ApprovalAttemptPort, type ApprovalHttpResponse } from "./p0b-hitl-http-retry";

const ITEM = "document-1";
const ROW = "review-row-1";
const NOT_READY = "Review 7b1 is not ready for a decision: its analysis candidate is still being prepared. Retry shortly.";

function response(status: number, body: unknown): ApprovalHttpResponse {
  return { ok: () => status >= 200 && status < 300, status: () => status, json: async () => body };
}

function scripted(responses: ApprovalHttpResponse[], opts: { deadline?: number; delay?: number } = {}) {
  let time = 0;
  const calls: string[] = [];
  let confirmed = 0;
  let waits = 0;
  const port: ApprovalAttemptPort = {
    now: () => time,
    submitOnce: async (rowId, remaining) => {
      calls.push(rowId);
      expect(remaining).toBeGreaterThan(0);
      const next = responses.shift();
      if (!next) throw new Error("UNEXPECTED_EXTRA_APPROVAL");
      return next;
    },
    waitUntilReady: async () => { waits++; },
    delay: async (ms) => { time += opts.delay ?? ms; },
    confirmed: async () => { confirmed++; },
  };
  return { port, calls, counts: () => ({ confirmed, waits, time }) };
}

describe("P0b exact-row HTTP approval retry (same driver as Playwright)", () => {
  it("400 CandidateNotReadyError then 200 APPROVED: exactly two POST attempts, one success", async () => {
    const s = scripted([
      response(400, { detail: NOT_READY }),
      response(200, { item_id: ITEM, row_id: ROW, current_status: "APPROVED" }),
    ]);
    await approveWithHttpResponse(s.port, ITEM, ROW, 10_000);
    expect(s.calls).toEqual([ROW, ROW]);
    expect(s.counts()).toEqual({ confirmed: 1, waits: 1, time: 2_000 });
  });

  it.each([403, 409, 422, 500])("HTTP %i fails closed without retry", async (status) => {
    const s = scripted([response(status, { detail: NOT_READY })]);
    await expect(approveWithHttpResponse(s.port, ITEM, ROW, 10_000)).rejects.toThrow("P0B_HITL_APPROVAL_FAILED");
    expect(s.calls).toEqual([ROW]);
    expect(s.counts().confirmed).toBe(0);
  });

  it("unrelated HTTP 400 fails closed without retry", async () => {
    const s = scripted([response(400, { detail: "Forbidden or invalid reviewer identity" })]);
    await expect(approveWithHttpResponse(s.port, ITEM, ROW, 10_000)).rejects.toThrow("P0B_HITL_APPROVAL_FAILED");
    expect(s.calls).toEqual([ROW]);
  });

  it.each([
    { item_id: "wrong-item", row_id: ROW, current_status: "APPROVED" },
    { item_id: ITEM, row_id: "wrong-row", current_status: "APPROVED" },
    { item_id: ITEM, row_id: ROW, current_status: "PENDING" },
  ])("HTTP 200 wrong identity/status fails closed: %j", async (body) => {
    const s = scripted([response(200, body)]);
    await expect(approveWithHttpResponse(s.port, ITEM, ROW, 10_000)).rejects.toThrow("P0B_HITL_APPROVAL_RESPONSE_MISMATCH");
    expect(s.calls).toEqual([ROW]);
    expect(s.counts().confirmed).toBe(0);
  });

  it("repeated transient responses stop at shared deadline", async () => {
    const s = scripted([response(400, { detail: NOT_READY }), response(400, { detail: NOT_READY })]);
    await expect(approveWithHttpResponse(s.port, ITEM, ROW, 3_000)).rejects.toThrow("P0B_HITL_APPROVAL_TIMEOUT");
    expect(s.calls).toEqual([ROW, ROW]);
    expect(s.counts().confirmed).toBe(0);
  });

  it("expired shared deadline never submits", async () => {
    const s = scripted([]);
    await expect(approveWithHttpResponse(s.port, ITEM, ROW, 0)).rejects.toThrow("P0B_HITL_APPROVAL_TIMEOUT");
    expect(s.calls).toHaveLength(0);
  });
});
