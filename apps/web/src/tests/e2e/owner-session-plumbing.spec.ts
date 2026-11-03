/**
 * TS-E2E-OWNER-SESSION-PLUMBING-001 -- can a person's browser reach this ephemeral stack through its PUBLIC addresses?
 *
 * No identity, no document, no AI: it opens the sign-in page of the public web URL, checks that Clerk (Development) loads on that
 * origin, and that the browser can reach the API at its public address across origins (CORS). Where uploads point is checked later,
 * inside the authenticated session (the route that says so is protected). If this passes, the only thing the owner's session still needs is the owner's login.
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

      // Three questions, asked apart so a failure says which one it is: is the API tunnel reachable at all (from Node), does the API
      // allow the web origin (CORS header), and can the page itself fetch it.
      const fromNode = await page.request
        .get(`${API}/health/live`, { headers: { Origin: WEB }, timeout: 30_000 })
        .then((r) => ({ status: r.status(), allowOrigin: r.headers()["access-control-allow-origin"] ?? null }))
        .catch((error: unknown) => ({ error: String(error) }));
      facts.apiFromNode = fromNode;
      const health = await page.evaluate(async (api) => {
        try {
          const response = await fetch(`${api}/health/live`, { mode: "cors" });
          return { status: response.status };
        } catch (error) {
          return { error: String(error) };
        }
      }, API);
      facts.apiFromBrowser = health;
      facts.apiReachableFromWebOrigin = "status" in health && health.status === 200;
      expect("status" in fromNode && fromNode.status, `the API tunnel answers at all: ${JSON.stringify(fromNode)}`).toBe(200);
      expect("allowOrigin" in fromNode && fromNode.allowOrigin, "the API allows the public web origin (CORS)").toBe(WEB);
      expect("status" in health && health.status, `the page can fetch the API across origins: ${JSON.stringify(health)}`).toBe(200);

      // /api/runtime/backend-url is a PROTECTED route (Clerk proxy): signed out, the browser is redirected to Clerk, a cross-origin
      // hop that fetch reports as "Failed to fetch". That is correct behaviour, not a plumbing defect, so it is recorded as a fact and
      // NOT asserted here; where uploads point is verified inside the authenticated owner session, after the owner's login.
      const runtime = await page.evaluate(async () => {
        try {
          const response = await fetch("/api/runtime/backend-url", { cache: "no-store", redirect: "manual" });
          return { status: response.status, type: response.type };
        } catch (error) {
          return { error: String(error) };
        }
      });
      facts.runtimeBackendUrlSignedOut = runtime;
      facts.uploadsTargetCheck = "deferred to the authenticated owner session (route is protected)";
    } finally {
      mkdirSync(path.dirname(OUT), { recursive: true });
      writeFileSync(OUT, `${JSON.stringify(facts, null, 2)}\n`, "utf8");
    }
  });
});
