import { describe, expect, it } from "vitest";
import { isRetryableCandidateNotReady } from "./p0b-hitl-response";

const CHECKPOINT_NOT_READY =
  "Review 7b1 is not ready for a decision: its analysis candidate is still being prepared. Retry shortly.";

describe("P0b HITL approval response classification", () => {
  it("retries the actual backend CandidateNotReadyError only on HTTP 400", () => {
    expect(isRetryableCandidateNotReady(400, CHECKPOINT_NOT_READY)).toBe(true);
    expect(isRetryableCandidateNotReady(400, "Candidate not ready: checkpoint pending")).toBe(true);
    for (const status of [200, 401, 403, 404, 409, 422, 500, 503]) {
      expect(isRetryableCandidateNotReady(status, CHECKPOINT_NOT_READY)).toBe(false);
    }
  });

  it("fails closed for malformed binding, unrelated errors and generic not-ready messages", () => {
    for (const detail of [
      "Review 7b1 carries a malformed candidate binding",
      "Project is not ready for a decision",
      "Forbidden: reviewer lacks permission",
      "Request failed with status code 400",
      "Candidate approval rejected: wrong row",
      "",
      null,
      undefined,
      { message: CHECKPOINT_NOT_READY },
    ]) {
      expect(isRetryableCandidateNotReady(400, detail)).toBe(false);
    }
  });
});
