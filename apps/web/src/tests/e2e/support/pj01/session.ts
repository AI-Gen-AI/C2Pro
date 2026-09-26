/**
 * PJ-01 steps 1–2: real Clerk sign-in and project creation through the UI.
 *
 * Reuses the P0b auth support (`establishAuthenticatedSession`,
 * `assertProjectEntryContinuity`) instead of duplicating the Clerk bootstrap. The only
 * typed navigation in PJ-01 is the Clerk testing bootstrap inside `signInWithClerk`; from
 * `/projects` onwards every step is reached by clicking.
 */
import { expect, type Page } from "@playwright/test";

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

  const created = page.waitForResponse(
    isBrowserVisibleProjectCreateResponse,
    { timeout: 60_000 },
  );
  await createButton.click();
  const response = await created;
  expect(response.status(), "project creation must be accepted").toBeLessThan(300);

  // The wizard itself routes to the project's Documents page; no typed URL.
  await page.waitForURL(PROJECT_URL, { timeout: 60_000 });
  await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
  const projectId = page.url().match(PROJECT_URL)?.[1];
  if (!projectId) throw new Error("PJ01_PROJECT_ID_UNRESOLVED: project id missing from the Documents URL");
  return projectId;
}
