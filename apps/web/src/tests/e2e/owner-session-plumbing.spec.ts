/**
 * TS-E2E-OWNER-SESSION-PLUMBING-001 -- can a person's browser reach this ephemeral stack through its PUBLIC addresses?
 *
 * No identity, no document, no AI: it opens the sign-in page of the public web URL, checks that Clerk (Development) loads on that
 * origin, that the browser can reach the API at its public address across origins (CORS), and that the application tells the
 * browser to upload to that same public API. If this passes, the only thing the owner's session still needs is the owner's login.
 * Opt-in (the manual owner-session job sets OWNER_SESSION_WEB_URL / OWNER_SESSION_API_URL).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, test } from "@playwright/test";

const WEB = (process.env.OWNER_SESSION_WEB_URL ?? "").replace(/\/+$/, "");
const API = (process.env.OWNER_SESSION_API_URL ?? "").replace(/\/+$/, "");
const OUT = path.join(process.cwd(), "playwright-report", "owner-session-plumbing.json");

test.describe("TS-E2E-OWNER-SESSION-PLUMBING-001: public addresses of the owner session", () => {
  test("sign-in loads on the public origin, the API is reachable from it, uploads point at the public API", async ({ page }) => {
    test.setTimeout(240_000);
    expect(WEB.startsWith("https://") && API.startsWith("https://"), "OWNER_SESSION_WEB_URL and OWNER_SESSION_API_URL are required").toBe(true);
    const facts: Record<string, unknown> = { webOrigin: new URL(WEB).host, apiOrigin: new URL(API).host };
    try {
      await setupClerkTestingToken({ page });
      await page.goto(`${WEB}/sign-in`, { waitUntil: "domcontentloaded", timeout: 120_000 });
      await page.waitForFunction(() => window.Clerk?.loaded === true, undefined, { timeout: 120_000 });
      facts.clerkLoadedOnPublicOrigin = true;
      await expect(page.getByText(/sign in/i).first()).toBeVisible({ timeout: 60_000 });
      facts.signInFormVisible = true;

      const health = await page.evaluate(async (api) => {
        const response = await fetch(`${api}/health/live`, { mode: "cors" });
        return { status: response.status };
      }, API);
      facts.apiReachableFromWebOrigin = health.status === 200;
      expect(health.status, "the API answers the browser at its public address (CORS allows the web origin)").toBe(200);

      const runtime = await page.evaluate(async () => {
        const response = await fetch("/api/runtime/backend-url", { cache: "no-store" });
        return { status: response.status, body: (await response.json().catch(() => ({}))) as Record<string, unknown> };
      });
      facts.runtimeBackendUrlStatus = runtime.status;
      facts.uploadsTargetPublicApi = JSON.stringify(runtime.body).includes(new URL(API).host);
      expect(facts.uploadsTargetPublicApi, "the application tells the browser to upload to the PUBLIC API address").toBe(true);
    } finally {
      mkdirSync(path.dirname(OUT), { recursive: true });
      writeFileSync(OUT, `${JSON.stringify(facts, null, 2)}\n`, "utf8");
    }
  });
});
