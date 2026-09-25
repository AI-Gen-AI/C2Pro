import { describe, expect, it } from "vitest";

import { retryDelayForRequest, shouldRetryRequest } from "./retryPolicy";

const err = (status?: number, headers?: Record<string, unknown>) =>
  status === undefined ? {} : { response: { status, headers } };

describe("shouldRetryRequest — bounded, class-specific (single retry owner)", () => {
  it.each([400, 401, 403, 404, 409, 422])(
    "does NOT retry terminal client error %i (⇒ exactly one request)",
    (status) => {
      expect(shouldRetryRequest(0, err(status))).toBe(false);
    },
  );

  it("retries 429 but hard-caps the attempts", () => {
    expect(shouldRetryRequest(0, err(429))).toBe(true);
    expect(shouldRetryRequest(1, err(429))).toBe(true);
    expect(shouldRetryRequest(2, err(429))).toBe(false); // bounded — cannot storm
  });

  it("retries transient (408 / 5xx / network) but bounded", () => {
    for (const status of [408, 500, 502, 503]) {
      expect(shouldRetryRequest(0, err(status))).toBe(true);
      expect(shouldRetryRequest(3, err(status))).toBe(false);
    }
    expect(shouldRetryRequest(0, err(undefined))).toBe(true); // network / timeout
    expect(shouldRetryRequest(3, err(undefined))).toBe(false);
  });

  it("does not retry a success-shaped or 2xx/3xx error", () => {
    expect(shouldRetryRequest(0, err(200))).toBe(false);
    expect(shouldRetryRequest(0, err(304))).toBe(false);
  });
});

describe("retryDelayForRequest — respects Retry-After, caps backoff", () => {
  it("honours Retry-After (seconds) for 429", () => {
    expect(retryDelayForRequest(0, err(429, { "retry-after": "3" }))).toBe(3000);
    expect(retryDelayForRequest(0, err(429, { "Retry-After": "5" }))).toBe(5000);
  });

  it("uses capped exponential backoff without Retry-After", () => {
    expect(retryDelayForRequest(0, err(500))).toBe(1000);
    expect(retryDelayForRequest(2, err(500))).toBe(4000);
    expect(retryDelayForRequest(20, err(500))).toBeLessThanOrEqual(15_000);
  });
});
