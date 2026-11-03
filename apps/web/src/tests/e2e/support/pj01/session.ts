/**
 * PJ-01 steps 1–2: real Clerk sign-in and project creation through the UI.
 *
 * Reuses the P0b auth support (`establishAuthenticatedSession`,
 * `assertProjectEntryContinuity`) instead of duplicating the Clerk bootstrap. The only
 * typed navigation in PJ-01 is the Clerk testing bootstrap inside `signInWithClerk`; from
 * `/projects` onwards every step is reached by clicking.
 */
import { expect, type Page, type Request, type Response } from "@playwright/test";

import {
  assertProjectEntryContinuity,
  establishAuthenticatedSession,
  observeAuth,
  type AuthObservation,
} from "../p0b-auth";

const PROJECT_URL = /\/projects\/([0-9a-f-]{36})\/documents/;

/**
 * Exactly what {@link isBrowserVisibleProjectCreateResponse} consumes from a Playwright
 * `Response` -- not `Pick<Response, "url" | "request" | "ok">`, which drags in the full
 * `Request` return type of `.request()` (headers, frame, timing, ...) even though only
 * `.method()` is ever read. A real Playwright `Response` still satisfies this structurally,
 * so `page.waitForResponse(isBrowserVisibleProjectCreateResponse, ...)` is unaffected; a
 * test double only needs to shape up to this, not build a full `Request` mock.
 */
export interface BrowserVisibleResponseLike {
  url(): string;
  ok(): boolean;
  request(): { method(): string };
}

export function isBrowserVisibleProjectCreateResponse(
  response: BrowserVisibleResponseLike,
): boolean {
  return (
    response.request().method() === "POST" &&
    new URL(response.url()).pathname === "/api/projects" &&
    response.ok()
  );
}


interface ProjectCreateAttempt {
  atMs: number;
  /** HTTP status, or null when the request failed before any answer (network). */
  status: number | null;
  failure?: string;
  retryAfter: string | null;
  requestId: string | null;
}

function isProjectCreateRequest(method: string, url: string): boolean {
  return method === "POST" && new URL(url).pathname === "/api/projects";
}

/**
 * What the failed create looked like, so a red run names the layer instead of a bare timeout:
 * the answers the browser got (status, Retry-After, request id), whether the backend answers its
 * health probe from this same browser, whether Clerk holds a session (id only), and what the
 * wizard shows.
 */
async function describeProjectCreateFailure(
  page: Page,
  attempts: ProjectCreateAttempt[],
  summary: string,
): Promise<string> {
  const probe = await page
    .evaluate(async () => {
      const clerk = (window as unknown as { Clerk?: { loaded?: boolean; session?: { id?: string; status?: string } | null } }).Clerk;
      const answer = async (path: string): Promise<string> => {
        try {
          const response = await fetch(path, { cache: "no-store" });
          return String(response.status);
        } catch (error) {
          return `network:${String(error).slice(0, 80)}`;
        }
      };
      return {
        url: window.location.pathname,
        clerkLoaded: clerk?.loaded ?? null,
        clerkSession: clerk?.session ? `${clerk.session.id ?? "?"}:${clerk.session.status ?? "?"}` : null,
        health: await answer("/api/health"),
        projectsList: await answer("/api/projects"),
      };
    })
    .catch((error: unknown) => ({ probeFailed: String(error).slice(0, 120) }));
  const visible = await page
    .getByRole("dialog")
    .first()
    .innerText({ timeout: 2_000 })
    .then((text) => text.replace(/\s+/g, " ").slice(0, 300))
    .catch(() => "(no dialog visible)");
  return `PJ01_PROJECT_CREATE_FAILED: ${summary}. attempts=${JSON.stringify(attempts)} probe=${JSON.stringify(probe)} dialog=${JSON.stringify(visible)}`;
}

export async function signInAsJourneyUser(page: Page, baseURL: string): Promise<AuthObservation> {
  const observation = observeAuth(page, baseURL);
  await establishAuthenticatedSession(page, observation);
  return observation;
}

export async function createProjectThroughUi(
  page: Page,
  observation: AuthObservation,
  projectName: string,
): Promise<string> {
  // Clicks "New Project" and proves the wizard opened under a stable authenticated session.
  await assertProjectEntryContinuity(page, observation);

  await page.getByTestId("project-name-input").fill(projectName);
  await page.getByRole("button", { name: "Next step" }).click();
  await page.getByRole("button", { name: "Review project" }).click();

  const createButton = page.getByTestId("create-project-button");
  await expect(createButton).toBeEnabled({ timeout: 15_000 });

  // Observe EVERY answer to the create request, not only a successful one: a predicate that
  // matches only `ok()` turns a refusal into a silent 60 s timeout that says nothing about why.
  const attempts: ProjectCreateAttempt[] = [];
  const startedAt = Date.now();
  const onResponse = (response: Response): void => {
    if (!isProjectCreateRequest(response.request().method(), response.url())) return;
    const headers = response.headers();
    attempts.push({
      atMs: Date.now() - startedAt,
      status: response.status(),
      retryAfter: headers["retry-after"] ?? null,
      requestId: headers["x-request-id"] ?? null,
    });
  };
  const onRequestFailed = (request: Request): void => {
    if (!isProjectCreateRequest(request.method(), request.url())) return;
    attempts.push({ atMs: Date.now() - startedAt, status: null, failure: request.failure()?.errorText ?? "unknown", retryAfter: null, requestId: null });
  };
  page.on("response", onResponse);
  page.on("requestfailed", onRequestFailed);
  try {
    // A rate-limited answer carries the interval the API asks the client to wait; a person would
    // wait and press the button again. Anything else is not retried: it is the finding.
    const MAX_RATE_LIMIT_WAITS = 3;
    let rateLimitWaits = 0;
    for (;;) {
      const seen = attempts.length;
      await createButton.click();
      const deadline = Date.now() + 60_000;
      while (attempts.length === seen && Date.now() < deadline) await page.waitForTimeout(250);
      const answer = attempts.at(-1);
      if (attempts.length === seen || !answer) {
        throw new Error(await describeProjectCreateFailure(page, attempts, "no answer to the create request within 60 s"));
      }
      if (answer.status !== null && answer.status < 300) break;
      if (answer.status === 429 && rateLimitWaits < MAX_RATE_LIMIT_WAITS) {
        rateLimitWaits += 1;
        const waitSeconds = Math.min(Math.max(Number(answer.retryAfter) || 5, 1), 65);
        await page.waitForTimeout(waitSeconds * 1_000);
        await expect(createButton).toBeEnabled({ timeout: 15_000 });
        continue;
      }
      throw new Error(await describeProjectCreateFailure(page, attempts, "the create request was refused"));
    }
  } finally {
    page.off("response", onResponse);
    page.off("requestfailed", onRequestFailed);
  }
  if (attempts.some((attempt) => attempt.status === 429)) {
    // Recorded, never hidden: the project was created only after the API's own Retry-After.
    console.warn(`PJ01_PROJECT_CREATE_RATE_LIMITED ${JSON.stringify(attempts)}`);
  }

  // The wizard itself routes to the project's Documents page; no typed URL.
  await page.waitForURL(PROJECT_URL, { timeout: 60_000 });
  await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
  const projectId = page.url().match(PROJECT_URL)?.[1];
  if (!projectId) throw new Error("PJ01_PROJECT_ID_UNRESOLVED: project id missing from the Documents URL");
  return projectId;
}
