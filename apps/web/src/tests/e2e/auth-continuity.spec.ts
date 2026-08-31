/**
 * TS-E2E-AUTH-CONTINUITY-001 — does a setup-project session survive into a
 * chromium/storageState context?
 *
 * The P0b journey failed three times in the auth preamble, each time
 * differently, and each "fix" was a guess at signIn/signOut ordering. This gate
 * stops guessing: it isolates the one seam under suspicion —
 *
 *   auth.setup context -> serialized storageState -> new chromium context
 *   -> Next.js middleware authentication continuity
 *
 * — and nothing else. No project creation, no upload, no worker, no analysis.
 * It resolves in seconds, so the answer is cheap and unambiguous, and the
 * six-minute journey never runs against an auth path that cannot hold.
 *
 * Repository truth it builds on: auth.setup already does
 * setupClerkTestingToken -> clerk.signIn -> loads /projects -> validates the
 * session subject -> saves storageState, and playwright.config gives the
 * chromium project that storageState with a dependency on setup. So if
 * /projects holds in setup but not here, the loss is in serialization/restore
 * or in what the middleware reads — not in the credentials.
 *
 * DIAGNOSTICS ARE DELIBERATELY STRUCTURAL ONLY. Cookie names, domains, paths
 * and flags are reported; values never are. Clerk presence and subject are
 * reported; tokens never are. A failing auth test must not become a credential
 * disclosure.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const STORAGE_STATE = path.join(process.cwd(), "playwright", ".auth", "user.json");

/** Cookie identity WITHOUT its value. */
interface CookieShape {
  name: string;
  domain: string;
  cookiePath: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: string;
}

function shape(cookie: {
  name: string;
  domain: string;
  path: string;
  httpOnly?: boolean;
  secure?: boolean;
  sameSite?: string;
}): CookieShape {
  return {
    name: cookie.name,
    domain: cookie.domain,
    cookiePath: cookie.path,
    httpOnly: Boolean(cookie.httpOnly),
    secure: Boolean(cookie.secure),
    sameSite: cookie.sameSite ?? "unset",
  };
}

function sortByName(cookies: CookieShape[]): CookieShape[] {
  return [...cookies].sort((a, b) => a.name.localeCompare(b.name));
}

/** Cookie shapes auth.setup serialized, read straight from storageState. */
function storedCookieShapes(): CookieShape[] {
  try {
    const raw = JSON.parse(readFileSync(STORAGE_STATE, "utf8")) as {
      cookies?: Array<Parameters<typeof shape>[0]>;
    };
    return sortByName((raw.cookies ?? []).map(shape));
  } catch {
    return [];
  }
}

async function restoredCookieShapes(context: BrowserContext): Promise<CookieShape[]> {
  return sortByName((await context.cookies()).map(shape));
}

/** Session presence and subject only — never the token. */
async function sessionFacts(page: Page): Promise<{ present: boolean; subject: unknown }> {
  return page.evaluate(async () => {
    const clerk = window.Clerk;
    if (!clerk?.session) return { present: false, subject: null };
    const token = await clerk.session.getToken();
    if (!token) return { present: true, subject: null };
    const payload = token.split(".")[1];
    if (!payload) return { present: true, subject: null };
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    return {
      present: true,
      subject: (JSON.parse(atob(normalized)) as { sub?: unknown }).sub ?? null,
    };
  });
}

test.describe("TS-E2E-AUTH-CONTINUITY-001: storageState session survives into chromium", () => {
  test.describe.configure({ timeout: 90_000 });

  test("a restored session stays on /projects instead of bouncing to sign-in", async ({
    page,
    context,
  }) => {
    // Document-level responses only: this is the redirect chain the middleware
    // actually drives, before any client-side routing.
    const documentChain: Array<{ url: string; status: number }> = [];
    page.on("response", (response) => {
      if (response.request().resourceType() === "document") {
        documentChain.push({ url: response.url(), status: response.status() });
      }
    });

    const cookiesBeforeToken = await restoredCookieShapes(context);
    await setupClerkTestingToken({ page });
    const cookiesAfterToken = await restoredCookieShapes(context);

    const requestedUrl = "/projects";
    const response = await page.goto(requestedUrl, { waitUntil: "domcontentloaded" });

    // A middleware redirect is visible on the FIRST document response, before
    // hydration. A client-side bounce shows up only in the later chain.
    const firstDocumentStatus = response?.status() ?? null;
    const redirectedServerSide = (response?.request().redirectedFrom() ?? null) !== null;
    const finalUrl = page.url();

    const facts = await sessionFacts(page).catch(() => ({ present: false, subject: null }));

    const diagnostics = {
      requestedUrl,
      finalUrl,
      firstDocumentStatus,
      redirectedServerSide,
      redirectChain: documentChain,
      clerkSessionPresent: facts.present,
      clerkSubject: facts.subject,
      storageStateCookies: storedCookieShapes(),
      restoredCookiesBeforeTestingToken: cookiesBeforeToken,
      restoredCookiesAfterTestingToken: cookiesAfterToken,
      storedButNotRestored: storedCookieShapes()
        .filter((s) => !cookiesAfterToken.some((r) => r.name === s.name && r.domain === s.domain))
        .map((c) => c.name),
      restoredButNotStored: cookiesAfterToken
        .filter((r) => !storedCookieShapes().some((s) => s.name === r.name && s.domain === r.domain))
        .map((c) => c.name),
    };

    expect(
      finalUrl,
      `Auth continuity broken. Structural diagnostics (no cookie values, no tokens):\n${JSON.stringify(
        diagnostics,
        null,
        2,
      )}`,
    ).not.toContain("/sign-in");

    await expect(page.locator('h1:has-text("Projects")')).toBeVisible({ timeout: 20_000 });
  });
});
