/**
 * The canonical P0b authentication + project-entry preamble, in ONE place.
 *
 * A standalone spec cannot license the journey: separate Playwright tests get
 * separate browser contexts, so a green micro-gate proves nothing about the run
 * that follows it. The acceptance authority is therefore
 * assertProjectEntryContinuity() called INSIDE the canonical journey, in the same
 * test, page and context, before any project creation, upload or worker work.
 * The standalone spec keeps these helpers only as a cheap diagnostic.
 *
 * Sequence (no sign-in): the chromium project restores the storageState that
 * auth.setup produced, so the session already exists. It needs only the testing
 * token, which the Clerk development instance requires before honouring it.
 *
 *   restored storageState -> setupClerkTestingToken -> / -> Clerk.loaded
 *   -> session present -> /projects -> Projects visible
 *   -> stability window -> New Project -> project-name-input editable
 *
 * DIAGNOSTICS ARE STRUCTURAL ONLY. Cookie names and flags are reported, and
 * values are compared internally to emit change booleans -- never the values
 * themselves, never a hash of them. Session identity comes from Clerk's typed
 * client state (Clerk.user.id / Clerk.session.id / .status per @clerk/shared),
 * never from decoding a JWT. A failing auth test must not become a credential
 * disclosure.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, type BrowserContext, type Page } from "@playwright/test";

const STORAGE_STATE = path.join(process.cwd(), "playwright", ".auth", "user.json");

/** How long /projects must hold a session with no interaction at all. */
const STABILITY_WINDOW_MS = 4_000;
/** Bounded race after the click: seconds, never the journey's minutes. */
const ENTRY_RACE_MS = 20_000;

interface RawCookie {
  name: string;
  value: string;
  domain: string;
  path: string;
  httpOnly?: boolean;
  secure?: boolean;
  sameSite?: string;
}

/** Cookie identity and flags WITHOUT its value. */
export interface CookieShape {
  name: string;
  domain: string;
  cookiePath: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: string;
}

function shape(cookie: RawCookie): CookieShape {
  return {
    name: cookie.name,
    domain: cookie.domain,
    cookiePath: cookie.path,
    httpOnly: Boolean(cookie.httpOnly),
    secure: Boolean(cookie.secure),
    sameSite: cookie.sameSite ?? "unset",
  };
}

function key(cookie: { name: string; domain: string }): string {
  return `${cookie.name}@${cookie.domain}`;
}

function readStoredCookies(): RawCookie[] {
  try {
    const raw = JSON.parse(readFileSync(STORAGE_STATE, "utf8")) as { cookies?: RawCookie[] };
    return raw.cookies ?? [];
  } catch {
    return [];
  }
}

/**
 * Session identity from Clerk's typed client state.
 *
 * Deliberately does NOT decode the session JWT: the diagnostic has no need to
 * interpret an unverified token, and hand-rolled base64/JSON parsing of one is a
 * security-sensitive construct with no upside here.
 */
export async function sessionFacts(page: Page): Promise<{
  present: boolean;
  userId: string | null;
  sessionId: string | null;
  sessionStatus: string | null;
}> {
  return page
    .evaluate(() => {
      const clerk = window.Clerk;
      return {
        present: Boolean(clerk?.session),
        userId: clerk?.user?.id ?? null,
        sessionId: clerk?.session?.id ?? null,
        sessionStatus: (clerk?.session?.status as string | undefined) ?? null,
      };
    })
    .catch(() => ({ present: false, userId: null, sessionId: null, sessionStatus: null }));
}

export interface MainFrameHop {
  url: string;
  status: number;
  at: number;
}

/**
 * Record MAIN-FRAME document responses only.
 *
 * Filtering on resourceType alone mixes iframe documents into the chain, so a
 * middleware redirect of the page cannot be told apart from an embedded frame
 * loading. Clerk renders iframes, which makes that distinction essential here.
 */
export function recordMainFrameNavigations(page: Page): MainFrameHop[] {
  const hops: MainFrameHop[] = [];
  page.on("response", (response) => {
    const request = response.request();
    if (request.resourceType() !== "document") return;
    if (request.frame() !== page.mainFrame()) return;
    hops.push({ url: response.url(), status: response.status(), at: Date.now() });
  });
  return hops;
}

export interface AuthSnapshot {
  label: string;
  at: number;
  url: string;
  clerkSessionPresent: boolean;
  clerkUserId: string | null;
  clerkSessionId: string | null;
  clerkSessionStatus: string | null;
  cookieShapes: CookieShape[];
  missingFromStorageState: string[];
  addedSinceStorageState: string[];
  /** Names whose value differs from the storageState value. Values never emitted. */
  changedCookieNames: string[];
  unchangedCookieNames: string[];
  /** True when any Clerk session-bearing cookie value changed. */
  sessionCookieChanged: boolean;
}

const SESSION_COOKIE_PREFIXES = ["__session", "__client_uat", "__clerk_db_jwt"];

/**
 * Structural snapshot. Cookie VALUES are compared in-process to produce change
 * booleans; they are never returned, logged or hashed.
 */
export async function authSnapshot(
  label: string,
  page: Page,
  context: BrowserContext,
): Promise<AuthSnapshot> {
  const facts = await sessionFacts(page);
  const live = (await context.cookies()) as RawCookie[];
  const stored = readStoredCookies();

  const storedByKey = new Map(stored.map((c) => [key(c), c]));
  const liveByKey = new Map(live.map((c) => [key(c), c]));

  const changed: string[] = [];
  const unchanged: string[] = [];
  for (const [k, storedCookie] of storedByKey) {
    const liveCookie = liveByKey.get(k);
    if (!liveCookie) continue;
    // Equality only. The values themselves never leave this scope.
    (liveCookie.value === storedCookie.value ? unchanged : changed).push(storedCookie.name);
  }

  return {
    label,
    at: Date.now(),
    url: page.url(),
    clerkSessionPresent: facts.present,
    clerkUserId: facts.userId,
    clerkSessionId: facts.sessionId,
    clerkSessionStatus: facts.sessionStatus,
    cookieShapes: live.map(shape).sort((a, b) => a.name.localeCompare(b.name)),
    missingFromStorageState: [...storedByKey.keys()]
      .filter((k) => !liveByKey.has(k))
      .map((k) => k.split("@")[0]!),
    addedSinceStorageState: [...liveByKey.keys()]
      .filter((k) => !storedByKey.has(k))
      .map((k) => k.split("@")[0]!),
    changedCookieNames: [...new Set(changed)].sort(),
    unchangedCookieNames: [...new Set(unchanged)].sort(),
    sessionCookieChanged: changed.some((name) =>
      SESSION_COOKIE_PREFIXES.some((prefix) => name.startsWith(prefix)),
    ),
  };
}

function compact(snapshots: AuthSnapshot[]): Array<Record<string, unknown>> {
  return snapshots.map((s) => ({
    label: s.label,
    url: s.url,
    clerkSessionPresent: s.clerkSessionPresent,
    clerkSessionStatus: s.clerkSessionStatus,
    hasUserId: s.clerkUserId !== null,
    hasSessionId: s.clerkSessionId !== null,
    sessionCookieChanged: s.sessionCookieChanged,
    changedCookieNames: s.changedCookieNames,
    missingFromStorageState: s.missingFromStorageState,
  }));
}

/** Step 1: the authenticated session, up to a rendered /projects. */
export async function establishAuthenticatedSession(page: Page): Promise<void> {
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await page.waitForFunction(() => window.Clerk?.loaded === true);

  const facts = await sessionFacts(page);
  expect(facts.present, "storageState from auth.setup must restore a live Clerk session").toBe(
    true,
  );

  await page.goto("/projects");
  await expect(page.locator('h1:has-text("Projects")')).toBeVisible({ timeout: 30_000 });
}

/**
 * Step 2: prove the session survives project entry, and LEAVE THE PAGE THERE.
 *
 * The journey continues from this exact state rather than repeating the
 * transition, so the gate is the journey's own first step and cannot drift from
 * it. Returns only once project-name-input is genuinely editable; otherwise
 * fails in ~20s with structural evidence instead of burning the journey timeout.
 */
export async function assertProjectEntryContinuity(
  page: Page,
  context: BrowserContext,
  mainFrameHops: MainFrameHop[],
): Promise<void> {
  const afterProjects = await authSnapshot("after /projects", page, context);

  // Does the session survive with NO interaction at all? If it dies here, the
  // click is not the cause and clicking would only muddy the evidence.
  await page.waitForTimeout(STABILITY_WINDOW_MS);
  const afterIdle = await authSnapshot("after idle stability window", page, context);

  if (!afterIdle.clerkSessionPresent) {
    expect(
      afterIdle.clerkSessionPresent,
      `Session lost on /projects with NO interaction -> background/session-revalidation failure, not the click.\n${JSON.stringify(
        { SUMMARY: compact([afterProjects, afterIdle]), mainFrameHops },
        null,
        2,
      )}`,
    ).toBe(true);
  }

  // Arm observers BEFORE the click, and stamp the clock BEFORE it, so a
  // navigation that happens DURING the click is still attributable to it.
  const input = page.getByTestId("project-name-input");
  const signedOut = page.waitForURL(/\/sign-in/, { timeout: ENTRY_RACE_MS }).then(() => "sign-in");
  const editable = input
    .waitFor({ state: "visible", timeout: ENTRY_RACE_MS })
    .then(() => "input");

  const clickStartedAt = Date.now();
  await page.getByRole("button", { name: /new project|create project/i }).first().click();
  const immediatelyAfterClick = await authSnapshot("immediately after click", page, context);

  const outcome = await Promise.race([editable, signedOut]).catch(() => "timeout");

  if (outcome !== "input") {
    const atTransition = await authSnapshot("at first main-frame transition", page, context);
    const firstHop = mainFrameHops.find((hop) => hop.at >= clickStartedAt) ?? null;

    expect(
      outcome,
      `Project entry lost the session. Structural diagnostics (no cookie values, no tokens):\n${JSON.stringify(
        {
          SUMMARY: compact([afterProjects, afterIdle, immediatelyAfterClick, atTransition]),
          outcome,
          clickStartedAt,
          firstMainFrameHopAfterClick: firstHop,
          msFromClickToFirstMainFrameNavigation: firstHop ? firstHop.at - clickStartedAt : null,
          // A main-frame document response after the click is a server-side
          // redirect; its absence means the bounce was client-side routing.
          redirectWasServerSide: firstHop !== null,
          mainFrameHops,
          fullSnapshots: [afterProjects, afterIdle, immediatelyAfterClick, atTransition],
        },
        null,
        2,
      )}`,
    ).toBe("input");
  }

  await expect(input).toBeEditable({ timeout: 5_000 });
  expect(page.url(), "must remain on an authenticated route").not.toContain("/sign-in");
}
