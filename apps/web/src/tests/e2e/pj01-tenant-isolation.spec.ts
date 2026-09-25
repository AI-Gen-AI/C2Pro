/**
 * TS-E2E-PJ01-002 — PJ-01 browser isolation.
 *
 * - Anonymous: a signed-out browser opening the PJ-01 project is sent to sign-in, never shown data.
 * - Tenant B: a second, independently authenticated Clerk organization opening tenant A's PJ-01
 *   project gets a neutral not-found state and none of tenant A's data.
 *
 * Tenant B needs its own Clerk test identity (E2E_CLERK_TENANT_B_USER_EMAIL, provisioned in a
 * different Organization). Without it the tenant-B test is SKIPPED and must be reported as
 * TENANT_ISOLATION_BROWSER=NOT_RUN — it is never simulated.
 */
import { existsSync, readFileSync } from "node:fs";

import { clerk } from "@clerk/testing/playwright";
import { expect, test } from "@playwright/test";

import { PJ01_PROJECT_ID_FILE } from "./support/pj01/journey";

const TENANT_B_EMAIL = process.env.E2E_CLERK_TENANT_B_USER_EMAIL;

function journeyProjectId(): string {
  if (!existsSync(PJ01_PROJECT_ID_FILE)) {
    throw new Error(`PJ01_ISOLATION_NO_PROJECT: run the PJ-01 journey first (${PJ01_PROJECT_ID_FILE})`);
  }
  return readFileSync(PJ01_PROJECT_ID_FILE, "utf8").trim();
}

test.describe("TS-E2E-PJ01-002: PJ-01 browser isolation", () => {
  test.describe.configure({ mode: "serial" });

  test("an anonymous browser is sent to sign-in and sees no project data", async ({ browser, baseURL }) => {
    const projectId = journeyProjectId();
    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();
    const apiStatuses: number[] = [];
    page.on("response", (response) => {
      if (response.url().includes(`/projects/${projectId}`) && response.url().includes("/api/")) apiStatuses.push(response.status());
    });
    await page.goto(`/projects/${projectId}/documents`);
    await expect(page).toHaveURL(/sign-in/, { timeout: 30_000 });
    expect(apiStatuses.every((status) => status === 401 || status === 403)).toBe(true);
    await context.close();
  });

  test("tenant B gets a neutral not-found for tenant A's project", async ({ browser, baseURL }) => {
    test.skip(!TENANT_B_EMAIL, "TENANT_ISOLATION_BROWSER=NOT_RUN: no second independently authenticated Clerk tenant fixture");
    const projectId = journeyProjectId();
    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();
    await page.goto("/");
    await clerk.signIn({ page, emailAddress: TENANT_B_EMAIL! });

    const projectResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname.endsWith(`/projects/${projectId}`) && response.request().method() === "GET",
      { timeout: 60_000 },
    );
    await page.goto(`/projects/${projectId}`);
    expect((await projectResponse).status()).toBe(404);
    await expect(page.getByText(/PJ-01/)).toHaveCount(0);
    await context.close();
  });
});
