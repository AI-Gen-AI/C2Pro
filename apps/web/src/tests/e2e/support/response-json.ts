/**
 * Read an API response's JSON body at the moment the response arrives.
 *
 * `page.waitForResponse(...)` resolves when the response HEADERS arrive; awaiting `.json()` only after
 * `page.goto(...)` has settled asks the browser for a body it may already have released once the page
 * navigated or re-fetched. That surfaces as `Protocol error (Network.getResponseBody): No resource with
 * given identifier found`, a lost body that says nothing about the backend. Starting the read in the
 * `response` listener, before any navigation can finish, removes that race. A body that still cannot be
 * read is reported as such, never retried silently.
 */
import type { Page, Response } from "@playwright/test";

function safelyMatches(predicate: (response: Response) => boolean, response: Response): boolean {
  try {
    return predicate(response);
  } catch {
    return false;
  }
}

export function captureJsonResponse<T>(
  page: Page,
  predicate: (response: Response) => boolean,
  options: { timeout?: number; label?: string } = {},
): Promise<T> {
  const timeout = options.timeout ?? 60_000;
  const label = options.label ?? "response";
  const captured = new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      page.off("response", onResponse);
      reject(new Error(`CAPTURE_JSON_TIMEOUT: no ${label} within ${timeout} ms`));
    }, timeout);
    const onResponse = (response: Response): void => {
      if (!safelyMatches(predicate, response)) return;
      page.off("response", onResponse);
      clearTimeout(timer);
      response.json().then(
        (body) => resolve(body as T),
        (error: unknown) =>
          reject(new Error(`CAPTURE_JSON_BODY_UNREADABLE: ${label} (HTTP ${response.status()}): ${String(error).slice(0, 200)}`)),
      );
    };
    page.on("response", onResponse);
  });
  // The caller awaits after navigating; a rejection that lands first must not be reported as unhandled.
  captured.catch(() => undefined);
  return captured;
}
