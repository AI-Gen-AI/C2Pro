/**
 * Authenticated API access for the integral S1–S8 runner.
 *
 * Every call carries the Clerk session of THE PAGE that makes it: the bearer token is read inside the page callback
 * and never returned to Node, logged or stored. A call is a genuine request of the signed-in user, not a back door.
 */
import type { Page } from "@playwright/test";

export interface ApiAnswer {
  status: number;
  data: unknown;
}

export async function callApi(
  page: Page,
  url: string,
  method: "GET" | "POST" | "PATCH" = "GET",
  body?: Record<string, unknown>,
): Promise<ApiAnswer> {
  return page.evaluate(
    async ({ target, verb, payload }) => {
      const token = await window.Clerk?.session?.getToken();
      if (!token) throw new Error("INTEGRAL_CLERK_SESSION_TOKEN_MISSING");
      const response = await fetch(target, {
        method: verb,
        headers: { Authorization: `Bearer ${token}`, ...(payload ? { "Content-Type": "application/json" } : {}) },
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      });
      const text = await response.text();
      let data: unknown = text;
      try {
        data = JSON.parse(text);
      } catch {
        /* keep the text */
      }
      return { status: response.status, data };
    },
    { target: url, verb: method, payload: body },
  );
}

export type Json = Record<string, unknown>;

export function itemsOf(data: unknown): Json[] {
  if (Array.isArray(data)) return data as Json[];
  const items = (data as { items?: unknown } | null)?.items;
  return Array.isArray(items) ? (items as Json[]) : [];
}

export const str = (value: unknown): string => (typeof value === "string" ? value : "");
export const strOrNull = (value: unknown): string | null => (typeof value === "string" ? value : null);

/** A bounded, readable poll: the last observed value is part of the failure, not just "timed out". */
export async function waitFor<T>(
  page: Page,
  description: string,
  probe: () => Promise<T | null | undefined | false>,
  options: { timeoutMs: number; intervalMs?: number },
): Promise<T> {
  const deadline = Date.now() + options.timeoutMs;
  for (;;) {
    const value = await probe();
    if (value) return value;
    if (Date.now() > deadline) throw new Error(`INTEGRAL_TIMEOUT: ${description} within ${options.timeoutMs} ms`);
    await page.waitForTimeout(options.intervalMs ?? 3_000);
  }
}
