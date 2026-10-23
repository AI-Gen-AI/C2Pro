import { describe, expect, it } from "vitest";

import {
  approveWithCandidateRetry,
  CandidateNotReadyError,
  classifyApprovalError,
  HitlApprovalFailedError,
  HitlApprovalTimeoutError,
  type ApprovalClock,
  type ApprovalPort,
  type DialogSnapshot,
} from "./p0b-hitl-approval";

const BACKEND_NOT_READY =
  "Review 7b1 is not ready for a decision: its analysis candidate is still being prepared. Retry shortly.";

function fakeClock(): ApprovalClock & { t: number } {
  const clock = {
    t: 0,
    now: () => clock.t,
    sleep: async (ms: number) => {
      clock.t += ms;
    },
  };
  return clock;
}

/**
 * Scripted dialog: each click starts a submission that is "pending" for
 * `pendingPolls` snapshots, then settles with the next scripted result.
 */
function scriptedPort(
  results: Array<"success" | string>,
  opts: {
    pendingPolls?: number;
    initialAlert?: string | null;
    neverSettle?: boolean;
    /** Snapshots after a click that still show the previous alert. */
    staleSnapshots?: number;
  } = {},
) {
  const pendingPolls = opts.pendingPolls ?? 1;
  let alert: string | null = opts.initialAlert ?? null;
  let open = true;
  let pending = 0;
  let stale = 0;
  let current: "success" | string | null = null;
  let clicks = 0;
  const port: ApprovalPort & { clicks: () => number } = {
    clicks: () => clicks,
    async clickConfirm() {
      clicks += 1;
      // The UI clears the previous error only once the request actually begins,
      // i.e. on the first poll after the click -- the old alert stays visible
      // until then (this is the stale-alert window).
      current = results[clicks - 1] ?? "unexpected extra click";
      pending = pendingPolls;
      stale = opts.staleSnapshots ?? 0;
    },
    async snapshot(): Promise<DialogSnapshot> {
      if (opts.neverSettle) return { dialogVisible: true, confirmDisabled: false, alertText: alert };
      if (current !== null && stale > 0) {
        stale -= 1;
        return { dialogVisible: open, confirmDisabled: false, alertText: alert };
      }
      if (current !== null && pending > 0) {
        pending -= 1;
        alert = null;
        return { dialogVisible: open, confirmDisabled: true, alertText: null };
      }
      if (current !== null) {
        if (current === "success") open = false;
        else alert = current;
        current = null;
      }
      return { dialogVisible: open, confirmDisabled: false, alertText: alert };
    },
  };
  return port;
}

describe("approveWithCandidateRetry", () => {
  it("retries a not-ready candidate with one click per attempt, then succeeds", async () => {
    const clock = fakeClock();
    const port = scriptedPort([BACKEND_NOT_READY, BACKEND_NOT_READY, "success"], { staleSnapshots: 1 });
    await approveWithCandidateRetry(port, clock, { deadlineMs: 120_000 });
    expect(port.clicks()).toBe(3);
  });

  it("fails closed on the first unknown error without retrying", async () => {
    const clock = fakeClock();
    const port = scriptedPort(["Forbidden: reviewer lacks permission", "success"]);
    await expect(approveWithCandidateRetry(port, clock, { deadlineMs: 120_000 })).rejects.toThrow(
      /P0B_HITL_APPROVAL_FAILED: Forbidden/,
    );
    expect(port.clicks()).toBe(1);
  });

  it("does not treat a stale not-ready alert from the previous attempt as the new result", async () => {
    const clock = fakeClock();
    // A not-ready alert is still on screen when the click happens; the real
    // submission then fails with an unknown error. A race that latches onto the
    // stale alert would retry and click twice; the driver must fail on attempt 1.
    const port = scriptedPort(["Conflict: stale candidate"], {
      initialAlert: BACKEND_NOT_READY,
      pendingPolls: 2,
      staleSnapshots: 2,
    });
    await expect(approveWithCandidateRetry(port, clock, { deadlineMs: 120_000 })).rejects.toBeInstanceOf(
      HitlApprovalFailedError,
    );
    expect(port.clicks()).toBe(1);
  });

  it("ignores a stale alert and succeeds when the new submission closes the dialog", async () => {
    const clock = fakeClock();
    const port = scriptedPort(["success"], { initialAlert: BACKEND_NOT_READY, pendingPolls: 2, staleSnapshots: 2 });
    await approveWithCandidateRetry(port, clock, { deadlineMs: 120_000 });
    expect(port.clicks()).toBe(1);
  });

  it("times out on a global deadline when the candidate never becomes ready", async () => {
    const clock = fakeClock();
    const port = scriptedPort(Array(200).fill(BACKEND_NOT_READY));
    await expect(approveWithCandidateRetry(port, clock, { deadlineMs: 20_000 })).rejects.toBeInstanceOf(
      HitlApprovalTimeoutError,
    );
    expect(clock.t).toBeLessThanOrEqual(20_000 + 250);
    expect(port.clicks()).toBeGreaterThan(1);
  });

  it("times out when a submission never settles", async () => {
    const clock = fakeClock();
    const port = scriptedPort(["success"], { neverSettle: true });
    await expect(approveWithCandidateRetry(port, clock, { deadlineMs: 5_000 })).rejects.toThrow(
      "P0B_HITL_APPROVAL_TIMEOUT",
    );
    expect(port.clicks()).toBe(1);
  });
});

describe("classifyApprovalError", () => {
  it("recognises the exact backend CandidateNotReadyError wording", () => {
    expect(classifyApprovalError(BACKEND_NOT_READY)).toBeInstanceOf(CandidateNotReadyError);
    expect(classifyApprovalError("Candidate not ready: checkpoint pending")).toBeInstanceOf(
      CandidateNotReadyError,
    );
  });

  it("does not classify unrelated errors, including malformed binding, as retryable", () => {
    for (const message of [
      "Review 7b1 carries a malformed candidate binding",
      "Request failed with status code 400",
      "Network Error",
    ]) {
      expect(classifyApprovalError(message)).toBeInstanceOf(HitlApprovalFailedError);
    }
  });
});
