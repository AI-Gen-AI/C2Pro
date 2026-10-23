/**
 * Deterministic HITL approval driver for the P0b journey.
 *
 * Each attempt is exactly ONE click on "Confirm approve" followed by the
 * observation of THAT submission's outcome. The only failure that is retried
 * is an explicit `CandidateNotReadyError` (the review row is visible before the
 * LangGraph checkpoint/candidate is durably bound). Every other failure is
 * fail-closed and surfaces immediately; the human-review pause is never skipped.
 *
 * The driver talks to the UI through a small port so the retry/deadline logic
 * can be tested without a browser or a clock.
 */

export class CandidateNotReadyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CandidateNotReadyError";
  }
}

export class HitlApprovalFailedError extends Error {
  constructor(message: string) {
    super(`P0B_HITL_APPROVAL_FAILED: ${message}`);
    this.name = "HitlApprovalFailedError";
  }
}

export class HitlApprovalTimeoutError extends Error {
  constructor() {
    super("P0B_HITL_APPROVAL_TIMEOUT");
    this.name = "HitlApprovalTimeoutError";
  }
}

/** What the confirm dialog looks like at one instant. */
export interface DialogSnapshot {
  dialogVisible: boolean;
  confirmDisabled: boolean;
  /** Text of the dialog alert, or null when no alert is rendered. */
  alertText: string | null;
}

export interface ApprovalPort {
  /** Perform exactly one click on the confirm button. */
  clickConfirm(): Promise<void>;
  snapshot(): Promise<DialogSnapshot>;
}

export interface ApprovalClock {
  now(): number;
  sleep(ms: number): Promise<void>;
}

export interface ApprovalOptions {
  /** Global deadline for the whole approval, across all attempts. */
  deadlineMs: number;
  retryDelayMs?: number;
  pollIntervalMs?: number;
}

/**
 * Backend wording: "Review <id> is not ready for a decision: its analysis
 * candidate is still being prepared. Retry shortly." (CandidateNotReadyError).
 */
const NOT_READY =
  /is not ready for a decision|candidate.{0,30}not.{0,20}ready|not.{0,20}ready.{0,60}candidate/i;

export function classifyApprovalError(message: string): Error {
  return NOT_READY.test(message)
    ? new CandidateNotReadyError(message)
    : new HitlApprovalFailedError(message);
}

type Outcome =
  | { kind: "closed" }
  | { kind: "error"; message: string };

/**
 * Observe the outcome of the submission that was JUST clicked.
 *
 * An alert already on screen before the click belongs to the previous attempt.
 * It is only trusted as this attempt's result once the submission has been seen
 * to start (button disabled, or the alert was cleared). Until then it is stale.
 */
async function observeSubmission(
  port: ApprovalPort,
  clock: ApprovalClock,
  deadline: number,
  pollIntervalMs: number,
): Promise<Outcome> {
  let started = false;
  for (;;) {
    const snap = await port.snapshot();
    if (!snap.dialogVisible) return { kind: "closed" };
    if (snap.confirmDisabled || snap.alertText === null) {
      started = true;
    } else if (started) {
      return { kind: "error", message: snap.alertText };
    }
    if (clock.now() >= deadline) throw new HitlApprovalTimeoutError();
    await clock.sleep(pollIntervalMs);
  }
}

export async function approveWithCandidateRetry(
  port: ApprovalPort,
  clock: ApprovalClock,
  options: ApprovalOptions,
): Promise<void> {
  const retryDelayMs = options.retryDelayMs ?? 2_000;
  const pollIntervalMs = options.pollIntervalMs ?? 250;
  const deadline = clock.now() + options.deadlineMs;

  for (;;) {
    if (clock.now() >= deadline) throw new HitlApprovalTimeoutError();
    await port.clickConfirm();
    const outcome = await observeSubmission(port, clock, deadline, pollIntervalMs);
    if (outcome.kind === "closed") return;

    const failure = classifyApprovalError(outcome.message);
    if (!(failure instanceof CandidateNotReadyError)) throw failure;
    if (clock.now() + retryDelayMs >= deadline) throw new HitlApprovalTimeoutError();
    await clock.sleep(retryDelayMs);
  }
}
