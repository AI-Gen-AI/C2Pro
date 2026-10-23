import { isRetryableCandidateNotReady } from "./p0b-hitl-response";

export interface ApprovalHttpResponse {
  ok(): boolean;
  status(): number;
  json(): Promise<unknown>;
}

export interface ApprovalAttemptPort {
  /** Register the exact-row HTTP waiter before clicking; resolve only that POST. */
  submitOnce(rowId: string, remainingMs: number): Promise<ApprovalHttpResponse>;
  waitUntilReady(remainingMs: number): Promise<void>;
  delay(ms: number): Promise<void>;
  confirmed(remainingMs: number): Promise<void>;
  now(): number;
}

/** The single approval retry loop used by the real Playwright journey. */
export async function approveWithHttpResponse(
  port: ApprovalAttemptPort,
  itemId: string,
  rowId: string,
  deadline: number,
  retryDelayMs = 2_000,
): Promise<void> {
  let attempts = 0;
  for (;;) {
    const remaining = deadline - port.now();
    if (remaining <= 0) throw new Error("P0B_HITL_APPROVAL_TIMEOUT");

    if (attempts >= 2) throw new Error("P0B_HITL_APPROVAL_RETRY_EXHAUSTED");
    attempts += 1;
    const response = await port.submitOnce(rowId, remaining);
    if (response.ok()) {
      const approved = await response.json().catch(() => null) as {
        item_id?: string; row_id?: string | null; current_status?: string;
      } | null;
      if (approved?.item_id !== itemId || approved?.row_id !== rowId ||
          approved?.current_status !== "APPROVED") {
        throw new Error("P0B_HITL_APPROVAL_RESPONSE_MISMATCH");
      }
      await port.confirmed(Math.max(1, deadline - port.now()));
      return;
    }

    const payload = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = typeof payload?.detail === "string" ? payload.detail : `HTTP ${response.status()}`;
    if (!isRetryableCandidateNotReady(response.status(), detail)) {
      throw new Error(`P0B_HITL_APPROVAL_FAILED: ${detail}`);
    }
    if (attempts >= 2) {
      throw new Error("P0B_HITL_APPROVAL_RETRY_EXHAUSTED");
    }
    if (port.now() + retryDelayMs >= deadline) {
      throw new Error("P0B_HITL_APPROVAL_TIMEOUT");
    }
    await port.waitUntilReady(Math.max(1, deadline - port.now()));
    await port.delay(retryDelayMs);
  }
}
