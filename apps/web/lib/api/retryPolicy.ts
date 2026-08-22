/**
 * Bounded, request-class-specific retry policy — the SINGLE retry owner (P0a.2).
 *
 * React Query's default retries every failure (including terminal 4xx) 3 times, which — stacked
 * across the several queries a page fires — produced the observed request storm and 429s. This
 * policy establishes one authoritative, bounded rule per request class:
 *
 *   - 400/401/403/404/409/422 (terminal client errors): never retried.
 *   - 429 (rate limited): bounded; honours `Retry-After` when supplied.
 *   - 408 / network / 5xx (transient): bounded with capped exponential backoff.
 *
 * Mutations opt out of automatic retries entirely (configured in queryClient), so queries and
 * mutations never inherit an identical policy.
 */

const MAX_TRANSIENT_RETRIES = 3; // network / 408 / 5xx
const MAX_RATE_LIMIT_RETRIES = 2; // 429
const MAX_BACKOFF_MS = 15_000;

function statusOf(error: unknown): number | undefined {
  if (typeof error === "object" && error !== null) {
    const response = (error as { response?: { status?: number } }).response;
    if (response && typeof response.status === "number") {
      return response.status;
    }
  }
  return undefined;
}

function retryAfterMs(error: unknown): number | undefined {
  if (typeof error === "object" && error !== null) {
    const headers = (error as { response?: { headers?: Record<string, unknown> } }).response
      ?.headers;
    const raw = headers?.["retry-after"] ?? headers?.["Retry-After"];
    if (typeof raw === "string" && raw.trim().length > 0) {
      const seconds = Number(raw);
      if (Number.isFinite(seconds) && seconds >= 0) {
        return Math.min(seconds * 1000, MAX_BACKOFF_MS);
      }
    }
  }
  return undefined;
}

/** React Query `retry` predicate: bounded, class-specific. Returns false ⇒ exactly one request. */
export function shouldRetryRequest(failureCount: number, error: unknown): boolean {
  const status = statusOf(error);
  if (status === undefined) {
    return failureCount < MAX_TRANSIENT_RETRIES; // network / timeout
  }
  if (status === 429) {
    return failureCount < MAX_RATE_LIMIT_RETRIES;
  }
  if (status === 408) {
    return failureCount < MAX_TRANSIENT_RETRIES; // request timeout = transient
  }
  if (status >= 400 && status < 500) {
    return false; // terminal: 400/401/403/404/409/422 — never retried
  }
  if (status >= 500) {
    return failureCount < MAX_TRANSIENT_RETRIES;
  }
  return false;
}

/** React Query `retryDelay`: honours `Retry-After` for 429, else capped exponential backoff. */
export function retryDelayForRequest(attemptIndex: number, error: unknown): number {
  const retryAfter = retryAfterMs(error);
  if (retryAfter !== undefined) {
    return retryAfter;
  }
  return Math.min(1000 * 2 ** attemptIndex, MAX_BACKOFF_MS);
}
