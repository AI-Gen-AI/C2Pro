/**
 * TS-E2E-PJ01-002 — PJ-01 browser isolation.
 *
 * Self-contained: it does not depend on the project another spec left behind (a failed journey
 * used to cascade into PJ01_ISOLATION_NO_PROJECT). The tenant-A project it protects is created
 * here through the real UI by the real Clerk E2E user; the other tenant's project is the seeded,
 * independently owned `…c3f1` project of a different tenant.
 *
 * - Anonymous: a signed-out browser opening the tenant-A project is sent to sign-in and the API
 *   answers 401/403 to every request for it — never data.
 * - Tenant A user -> tenant B's project: the signed-in E2E user opens another tenant's project and
 *   every API answer for it is 401/403/404, with none of its data on screen. One direction only:
 *   the E2E user cannot see the foreign project.
 * - Tenant B user -> tenant A's project: needs a second, independently authenticated Clerk
 *   identity (E2E_CLERK_TENANT_B_USER_EMAIL, in a different Organization). Without it the test is
 *   SKIPPED and must be reported as TENANT_ISOLATION_BROWSER_B_TO_A=NOT_RUN — never simulated.
 */
import { clerk } from "@clerk/testing/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";

const TENANT_B_EMAIL = process.env.E2E_CLERK_TENANT_B_USER_EMAIL;
const EMPTY_SESSION = { cookies: [], origins: [] };

// Seeded by apps/api/tests/e2e_seed/seed_wedge.py for a different tenant than the E2E user's.
const FOREIGN_PROJECT_ID = "00000000-0000-0000-0000-00000000c3f1";
const FOREIGN_PROJECT_NAME = "Foreign Tenant Confidential Project";

interface ApiStatus {
  url: string;
  status: number;
  /** Seconds the API asked the caller to wait (rate limiting only). */
  retryAfterSeconds?: number;
}

function recordApiStatuses(page: Page, projectId: string): ApiStatus[] {
  const statuses: ApiStatus[] = [];
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/") && url.pathname.includes(projectId)) {
      const retryAfter = Number(response.headers()["retry-after"]);
      statuses.push({
        url: url.pathname,
        status: response.status(),
        ...(Number.isFinite(retryAfter) ? { retryAfterSeconds: retryAfter } : {}),
      });
    }
  });
  return statuses;
}

/**
 * Open a project the caller must not see and return the API's AUTHORIZATION verdicts for it.
 *
 * The API rate-limits each user (a fixed one-minute window) and the journey that ran just before
 * used that user's budget up: a 429 says "too many requests", not "not yours", so it proves nothing
 * about isolation. When the API answers 429 the page is opened again only after the interval the
 * API itself asked for (Retry-After), never after a guessed delay, and a run that never obtains a
 * verdict fails as inconclusive instead of passing on a rate-limit answer.
 */
async function authorizationVerdicts(page: Page, statuses: ApiStatus[], projectId: string): Promise<ApiStatus[]> {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    statuses.length = 0;
    await page.goto(`/projects/${projectId}/documents`);
    await expect
      .poll(() => statuses.length, { timeout: 30_000, message: "the page must have asked the API about the project" })
      .toBeGreaterThan(0);
    const limited = statuses.filter((entry) => entry.status === 429);
    if (limited.length === 0) return [...statuses];
    const waitSeconds = Math.min(65, Math.max(...limited.map((entry) => entry.retryAfterSeconds ?? 60)));
    test.info().annotations.push({
      type: "rate-limited",
      description: `attempt ${attempt + 1}: API answered 429 (Retry-After ${waitSeconds}s); retrying after that interval`,
    });
    await page.waitForTimeout(waitSeconds * 1000);
  }
  const verdicts = statuses.filter((entry) => entry.status !== 429);
  if (verdicts.length === 0) throw new Error(`RATE_LIMITED_NO_VERDICT: ${JSON.stringify(statuses)}`);
  return [...statuses];
}

async function createOwnProject(browser: Browser, baseURL: string): Promise<string> {
  const context = await browser.newContext({ baseURL, storageState: EMPTY_SESSION });
  try {
    const page = await context.newPage();
    const observation = await signInAsJourneyUser(page, baseURL);
    return await createProjectThroughUi(page, observation, `PJ-01 isolation ${Date.now()}`);
  } finally {
    await context.close();
  }
}

test.describe("TS-E2E-PJ01-002: PJ-01 browser isolation", () => {
  test.describe.configure({ mode: "serial", timeout: 300_000 });

  let tenantAProjectId = "";

  test.beforeAll(async ({ browser, baseURL }) => {
    test.setTimeout(180_000); // sign-in + project wizard; hooks do not inherit the describe timeout
    tenantAProjectId = await createOwnProject(browser, baseURL ?? "http://localhost:3100");
  });

  test("an anonymous browser is sent to sign-in and sees no project data", async ({ browser, baseURL }) => {
    const context = await browser.newContext({ baseURL, storageState: EMPTY_SESSION });
    const page = await context.newPage();
    const statuses = recordApiStatuses(page, tenantAProjectId);
    await page.goto(`/projects/${tenantAProjectId}/documents`);
    await expect(page).toHaveURL(/sign-in/, { timeout: 30_000 });
    expect(
      statuses.filter((entry) => entry.status !== 401 && entry.status !== 403),
      `every API answer for the project must be a denial: ${JSON.stringify(statuses)}`,
    ).toEqual([]);
    await context.close();
  });

  test("the signed-in E2E user gets a denial for another tenant's project, with none of its data", async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext({ baseURL, storageState: EMPTY_SESSION });
    const page = await context.newPage();
    await signInAsJourneyUser(page, baseURL ?? "http://localhost:3100");
    const statuses = recordApiStatuses(page, FOREIGN_PROJECT_ID);
    const verdicts = await authorizationVerdicts(page, statuses, FOREIGN_PROJECT_ID);
    await expect(page.getByText(FOREIGN_PROJECT_NAME)).toHaveCount(0);
    expect(
      verdicts.filter((entry) => ![401, 403, 404].includes(entry.status)),
      `the API must deny every request for another tenant's project: ${JSON.stringify(verdicts)}`,
    ).toEqual([]);
    test.info().annotations.push({
      type: "tenant-isolation",
      description: `A->B denied: ${JSON.stringify(verdicts)}. B->A: ${TENANT_B_EMAIL ? "see next test" : "NOT_RUN (no second Clerk tenant identity)"}`,
    });
    await context.close();
  });

  test("tenant B gets a neutral not-found for tenant A's project", async ({ browser, baseURL }) => {
    test.skip(!TENANT_B_EMAIL, "TENANT_ISOLATION_BROWSER_B_TO_A=NOT_RUN: no second independently authenticated Clerk tenant fixture");
    const context = await browser.newContext({ baseURL, storageState: EMPTY_SESSION });
    const page = await context.newPage();
    await page.goto("/");
    await clerk.signIn({ page, emailAddress: TENANT_B_EMAIL! });

    const projectResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.endsWith(`/projects/${tenantAProjectId}`) && response.request().method() === "GET",
      { timeout: 60_000 },
    );
    await page.goto(`/projects/${tenantAProjectId}`);
    expect((await projectResponse).status()).toBe(404);
    await expect(page.getByText(/PJ-01/)).toHaveCount(0);
    await context.close();
  });
});
