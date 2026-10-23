/** Retry ONLY the checkpoint/candidate-readiness race; never bypass HITL. */
const CANDIDATE_NOT_READY =
  /\bis not ready for a decision:\s*its analysis candidate is still being prepared\b|\bcandidate\b.{0,30}\bnot\b.{0,20}\bready\b|\bnot\b.{0,20}\bready\b.{0,30}\bcandidate\b/i;

export function isRetryableCandidateNotReady(status: number, detail: unknown): boolean {
  return status === 400 && typeof detail === "string" && CANDIDATE_NOT_READY.test(detail);
}
