/**
 * The canonical P0b authentication + project-entry preamble, in ONE place.
 *
 * WHAT "AUTHENTICATED" MEANS HERE
 *
 * `Clerk.session.status === "active"` is NOT sufficient. C2Pro derives its
 * tenant from the ACTIVE Organization's metadata (`lib/clerk-tenant.ts`
 * `getTenantIdFromOrganizationMetadata`), and `AuthSync` auto-activates an
 * Organization only when the identity has exactly one membership. A
 * Clerk-signed-in user with no Organization has no tenant, so it cannot
 * represent the real journey. The gate therefore proves, together:
 *
 *   Clerk session active + Clerk user present + expected Organization active
 *   + that Organization's tenant_id matches the deterministic CI tenant
 *   + an application bearer seen on a same-origin API call
 *   + route still /projects + no same-origin API 401/403.
 *
 * BOOTSTRAP
 *
 * `clerk.signIn({ page, emailAddress })` — the flow the installed
 * @clerk/testing 2.2.7 documents (resolved from
 * dist/types/playwright/helpers.d.ts): Backend-API user lookup, short-lived
 * sign-in token, `ticket` strategy. No password, no first-factor form, no
 * inbox, no OTP, no credential literal. The journey signs in live in its own
 * page and context rather than restoring a serialized storageState.
 *
 * DIAGNOSTICS ARE STRUCTURAL ONLY. No tokens, JWTs, cookie values, passwords,
 * testing tokens or Organization ids are ever emitted. Identity, Organization
 * and tenant state come from Clerk's typed client resources
 * (`Clerk.session.status`, `Clerk.user.id`, `Clerk.organization`,
 * `Clerk.user.organizationMemberships`, `Clerk.organization.publicMetadata` per
 * @clerk/shared) — never from decoding a JWT. Identifiers are compared in
 * process and reported as booleans. A failing auth test must not become a
 * credential disclosure.
 */

import path from "node:path";

import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, type Page, type Response } from "@playwright/test";

export const AUTH_STATE_FILE = path.join(process.cwd(), "playwright", ".auth", "user.json");

/** The configured E2E identity. Reused, never replaced. */
export const E2E_USER_EMAIL = process.env.E2E_CLERK_USER_EMAIL ?? "testuser@c2pro.com";
/** Pin written by the fixture provisioner; falls back to the single membership. */
const EXPECTED_ORGANIZATION_ID = process.env.E2E_CLERK_ORGANIZATION_ID ?? null;
/** The deterministic CI tenant (apps/api/tests/e2e_seed/seed_wedge.py). */
const EXPECTED_TENANT_ID =
  process.env.E2E_EXPECTED_TENANT_ID ?? "00000000-0000-0000-0000-00000000a113";

/** How long /projects must hold every auth invariant with no interaction. */
const STABILITY_WINDOW_MS = 4_500;
const STABILITY_SAMPLE_MS = 250;
/** Bounded race after the click: seconds, never the journey's minutes. */
const ENTRY_RACE_MS = 20_000;
/** Bounded wait for AuthSync to activate the Organization after sign-in. */
const ORGANIZATION_SYNC_TIMEOUT_MS = 20_000;

export type AuthFailureClassification =
  | "SERVER_MIDDLEWARE_REDIRECT"
  | "CLIENT_API_401_REDIRECT"
  | "CLIENT_AUTH_STATE_REDIRECT"
  | "CLERK_ORG_SYNC_FAILURE"
  | "E2E_AUTH_BOOTSTRAP_DEFECT"
  | "UNCLASSIFIED";

export type TokenAcquisition = "GET_TOKEN_OK" | "GET_TOKEN_NULL" | "GET_TOKEN_ERROR";

// ---------------------------------------------------------------------------
// Clerk client state (typed resources only — no JWT decoding, no token values)
// ---------------------------------------------------------------------------

/** Raw read. Identifiers stay in this process and are never emitted. */
interface RawClerkState {
  loaded: boolean;
  sessionActive: boolean;
  sessionStatus: string | null;
  userPresent: boolean;
  organizationPresent: boolean;
  activeOrganizationId: string | null;
  activeOrganizationTenantId: string | null;
  membershipOrganizationIds: string[];
}

const EMPTY_CLERK_STATE: RawClerkState = {
  loaded: false,
  sessionActive: false,
  sessionStatus: null,
  userPresent: false,
  organizationPresent: false,
  activeOrganizationId: null,
  activeOrganizationTenantId: null,
  membershipOrganizationIds: [],
};

async function readRawClerkState(page: Page): Promise<RawClerkState> {
  return page
    .evaluate(() => {
      const clerkClient = window.Clerk;
      const memberships = clerkClient?.user?.organizationMemberships ?? [];
      const tenantId = clerkClient?.organization?.publicMetadata?.tenant_id;
      return {
        loaded: Boolean(clerkClient?.loaded),
        sessionActive: clerkClient?.session?.status === "active",
        sessionStatus: clerkClient?.session?.status ?? null,
        userPresent: Boolean(clerkClient?.user),
        organizationPresent: Boolean(clerkClient?.organization),
        activeOrganizationId: clerkClient?.organization?.id ?? null,
        activeOrganizationTenantId: typeof tenantId === "string" ? tenantId : null,
        membershipOrganizationIds: memberships.map((m) => m.organization.id),
      };
    })
    .catch(() => EMPTY_CLERK_STATE);
}

/** Safe, emittable Clerk facts. Booleans and counts only. */
export interface ClerkFacts {
  clerkLoaded: boolean;
  clerkSessionActive: boolean;
  clerkSessionStatus: string | null;
  clerkUserPresent: boolean;
  membershipPresent: boolean;
  membershipCount: number;
  organizationPresent: boolean;
  /** False when neither a pinned id nor exactly one membership resolves one. */
  expectedOrganizationResolvable: boolean;
  expectedOrganizationActive: boolean;
  /** The active Organization carries the deterministic CI tenant id. */
  expectedTenantIdActive: boolean;
}

function toFacts(raw: RawClerkState): ClerkFacts {
  const expectedId =
    EXPECTED_ORGANIZATION_ID ??
    (raw.membershipOrganizationIds.length === 1 ? raw.membershipOrganizationIds[0]! : null);

  return {
    clerkLoaded: raw.loaded,
    clerkSessionActive: raw.sessionActive,
    clerkSessionStatus: raw.sessionStatus,
    clerkUserPresent: raw.userPresent,
    membershipPresent: raw.membershipOrganizationIds.length > 0,
    membershipCount: raw.membershipOrganizationIds.length,
    organizationPresent: raw.organizationPresent,
    expectedOrganizationResolvable: expectedId !== null,
    // Identifiers are compared here; neither is ever emitted.
    expectedOrganizationActive: expectedId !== null && raw.activeOrganizationId === expectedId,
    expectedTenantIdActive: raw.activeOrganizationTenantId === EXPECTED_TENANT_ID,
  };
}

export async function clerkFacts(page: Page): Promise<ClerkFacts> {
  return toFacts(await readRawClerkState(page));
}

/**
 * Classify the exact call AuthSync makes, without ever returning its result.
 * `Clerk.session.getToken()` is the seam whose null/throw drives
 * handleAuthErrorStatus(401) -> window.location.assign("/sign-in").
 */
export async function classifyTokenAcquisition(page: Page): Promise<TokenAcquisition> {
  return page
    .evaluate<TokenAcquisition>(async () => {
      try {
        const token = await window.Clerk?.session?.getToken();
        return token ? "GET_TOKEN_OK" : "GET_TOKEN_NULL";
      } catch {
        return "GET_TOKEN_ERROR";
      }
    })
    .catch<TokenAcquisition>(() => "GET_TOKEN_ERROR");
}

// ---------------------------------------------------------------------------
// Navigation provenance + application-auth observation
// ---------------------------------------------------------------------------

function pathnameOf(url: string, base?: string): string {
  try {
    return new URL(url, base ?? "http://localhost").pathname;
  } catch {
    return url;
  }
}

export interface MainFrameHop {
  method: string;
  pathname: string;
  status: number;
  at: number;
  /**
   * Status of the response that redirected TO this one, when there was one.
   * A 3xx here means the server sent the browser somewhere; null means the
   * navigation was client-side. That single discriminator is what separates a
   * middleware redirect from window.location.assign(), which is the only thing
   * the fuller redirect-chain forensics were ever needed for.
   */
  redirectedFromStatus: number | null;
}

export interface ApiAuthFailure {
  pathname: string;
  method: string;
  status: number;
  at: number;
}

export interface AuthObservation {
  hops: () => Promise<MainFrameHop[]>;
  /** Same-origin /api responses with 401/403, oldest first. */
  apiAuthFailures: ApiAuthFailure[];
  /** True once a same-origin /api request carried an Authorization header. */
  applicationBearerObserved: () => boolean;
}

async function describeHop(response: Response): Promise<MainFrameHop> {
  const request = response.request();
  const from = request.redirectedFrom();
  const fromResponse = from ? await from.response().catch(() => null) : null;

  return {
    method: request.method(),
    pathname: pathnameOf(response.url()),
    status: response.status(),
    at: Date.now(),
    redirectedFromStatus: fromResponse?.status() ?? null,
  };
}

/**
 * Install the observers. Main-frame documents only: an iframe document (Clerk
 * renders several) cannot be told apart from a page transition otherwise.
 *
 * A main-frame document response with status 200 does NOT prove a server
 * redirect — `window.location.assign("/sign-in")`, which lib/api/client.ts
 * performs on a 401, produces exactly that. Only a genuine 3xx on the response
 * that redirected to it distinguishes the two, which is why that status is kept.
 */
export function observeAuth(page: Page, baseUrl: string): AuthObservation {
  const pending: Promise<MainFrameHop>[] = [];
  const apiAuthFailures: ApiAuthFailure[] = [];
  let bearerObserved = false;

  const origin = (() => {
    try {
      return new URL(baseUrl).origin;
    } catch {
      return null;
    }
  })();

  const isSameOriginApi = (url: string): boolean => {
    try {
      const parsed = new URL(url);
      if (origin !== null && parsed.origin !== origin) return false;
      return parsed.pathname.startsWith("/api");
    } catch {
      return false;
    }
  };

  page.on("request", (request) => {
    if (!isSameOriginApi(request.url())) return;
    // Presence only. The header value is never read into a variable, logged or
    // returned — this records that the application attached a bearer at all.
    if (request.headers()["authorization"]) bearerObserved = true;
  });

  page.on("response", (response) => {
    const request = response.request();

    if (isSameOriginApi(response.url())) {
      const status = response.status();
      if (status === 401 || status === 403) {
        apiAuthFailures.push({
          pathname: pathnameOf(response.url()),
          method: request.method(),
          status,
          at: Date.now(),
        });
      }
      return;
    }

    if (request.resourceType() !== "document") return;
    if (request.frame() !== page.mainFrame()) return;
    pending.push(describeHop(response));
  });

  return {
    hops: () => Promise.all(pending),
    apiAuthFailures,
    applicationBearerObserved: () => bearerObserved,
  };
}

// ---------------------------------------------------------------------------
// Bounded auth state at a point in time
// ---------------------------------------------------------------------------

export interface AuthPoint extends ClerkFacts {
  label: string;
  at: number;
  currentPath: string;
  applicationBearerObserved: boolean;
  firstSameOriginApiAuthFailure: ApiAuthFailure | null;
}

export async function authPoint(
  label: string,
  page: Page,
  observation: AuthObservation,
): Promise<AuthPoint> {
  return {
    label,
    at: Date.now(),
    currentPath: pathnameOf(page.url()),
    applicationBearerObserved: observation.applicationBearerObserved(),
    firstSameOriginApiAuthFailure: observation.apiAuthFailures[0] ?? null,
    ...(await clerkFacts(page)),
  };
}

// ---------------------------------------------------------------------------
// Failure classification
// ---------------------------------------------------------------------------

export interface ClassificationInput {
  hops: MainFrameHop[];
  apiAuthFailures: ApiAuthFailure[];
  points: AuthPoint[];
}

/**
 * Exactly one classification, or UNCLASSIFIED. Conditions are mutually
 * exclusive by construction so a weaker rule cannot swallow a stronger one; a
 * classification is never forced when the evidence does not carry it.
 */
export function classifyAuthFailure(input: ClassificationInput): AuthFailureClassification {
  const { hops, apiAuthFailures, points } = input;

  const signInHops = hops.filter((hop) => hop.pathname.startsWith("/sign-in"));
  if (signInHops.length === 0 && apiAuthFailures.length === 0) return "UNCLASSIFIED";

  const firstSignInHop = signInHops[0] ?? null;

  // A. /sign-in was reached THROUGH a genuine 3xx, i.e. the server sent us.
  const serverRedirect = signInHops.some(
    (hop) =>
      hop.redirectedFromStatus !== null &&
      hop.redirectedFromStatus >= 300 &&
      hop.redirectedFromStatus < 400,
  );
  if (serverRedirect) return "SERVER_MIDDLEWARE_REDIRECT";

  // B. A protected same-origin API 401 preceding a hard /sign-in navigation
  //    that itself carries no server redirect.
  const precedingUnauthorized = apiAuthFailures.find(
    (failure) => failure.status === 401 && (!firstSignInHop || failure.at <= firstSignInHop.at),
  );
  if (precedingUnauthorized && firstSignInHop && firstSignInHop.redirectedFromStatus === null) {
    return "CLIENT_API_401_REDIRECT";
  }

  // D. Clerk stayed active throughout, but the Organization, its tenant or the
  //    application bearer never stabilised before the transition.
  const clerkStayedActive = points.length > 0 && points.every((point) => point.clerkSessionActive);
  const tenancyUnstable = points.some(
    (point) =>
      !point.expectedOrganizationActive ||
      !point.expectedTenantIdActive ||
      !point.applicationBearerObserved,
  );
  if (clerkStayedActive && tenancyUnstable) return "CLERK_ORG_SYNC_FAILURE";

  // C. No server 3xx and no API 401, but auth state fell away and a client
  //    navigation to /sign-in followed.
  const authStateLost = points.some((point) => !point.clerkSessionActive);
  if (firstSignInHop && apiAuthFailures.length === 0 && authStateLost) {
    return "CLIENT_AUTH_STATE_REDIRECT";
  }

  return "UNCLASSIFIED";
}

// ---------------------------------------------------------------------------
// Step 1 — the documented Clerk bootstrap
// ---------------------------------------------------------------------------

/** Sign in live, in this page and context, with the documented installed API. */
export async function signInWithClerk(
  page: Page,
  observation?: AuthObservation,
): Promise<void> {
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await clerk.loaded({ page });

  await clerk.signIn({ page, emailAddress: E2E_USER_EMAIL });

  const afterSignIn = await clerkFacts(page);
  await requireAuthInvariant(
    afterSignIn.clerkUserPresent && afterSignIn.clerkSessionActive,
    "E2E_AUTH_BOOTSTRAP_DEFECT",
    `the documented Clerk bootstrap did not produce an active session ` +
      `(status=${afterSignIn.clerkSessionStatus}, userPresent=${afterSignIn.clerkUserPresent})`,
    page,
    observation,
  );
}

/**
 * The stricter C2Pro contract, required by the P0b gate and NOT by the shared
 * storageState setup: Clerk signed in is not the same as C2Pro authenticated,
 * because the tenant comes from the active Organization's metadata.
 */
export async function requireExpectedOrganization(
  page: Page,
  observation?: AuthObservation,
): Promise<void> {
  const memberships = await clerkFacts(page);
  await requireAuthInvariant(
    memberships.membershipPresent,
    "CLERK_ORG_SYNC_FAILURE",
    "the configured E2E identity holds no Organization membership, so there is no tenant " +
      "and no expected Organization to activate. Run the Clerk E2E fixture provisioner",
    page,
    observation,
  );

  // AuthSync (root layout, so mounted on "/" too) calls setActive() when exactly
  // one membership exists. Observe that landing; do NOT activate it here, which
  // would mask the seam this gate exists to prove.
  await page
    .waitForFunction(() => Boolean(window.Clerk?.organization), undefined, {
      timeout: ORGANIZATION_SYNC_TIMEOUT_MS,
    })
    .catch(() => undefined);

  const afterOrganization = await clerkFacts(page);
  await requireAuthInvariant(
    afterOrganization.expectedOrganizationResolvable,
    "CLERK_ORG_SYNC_FAILURE",
    `the expected Organization is unresolvable (memberships=${afterOrganization.membershipCount}); ` +
      "pin one with E2E_CLERK_ORGANIZATION_ID",
    page,
    observation,
  );
  await requireAuthInvariant(
    afterOrganization.expectedOrganizationActive,
    "CLERK_ORG_SYNC_FAILURE",
    "the expected Organization never became active within " +
      `${ORGANIZATION_SYNC_TIMEOUT_MS}ms while the Clerk session stayed active`,
    page,
    observation,
  );
  await requireAuthInvariant(
    afterOrganization.expectedTenantIdActive,
    "CLERK_ORG_SYNC_FAILURE",
    "the active Organization's publicMetadata.tenant_id does not match the deterministic " +
      "CI tenant, so the frontend would resolve a tenant the local database does not hold",
    page,
    observation,
  );
}

/** Sign in, prove the Organization and tenant, and land on a rendered /projects. */
export async function establishAuthenticatedSession(
  page: Page,
  observation?: AuthObservation,
): Promise<void> {
  await signInWithClerk(page, observation);
  await requireExpectedOrganization(page, observation);
  await openProjects(page);
}

/** Navigate to /projects and wait for it to render. */
export async function openProjects(page: Page): Promise<void> {
  await page.goto("/projects");
  await expect(page.locator('h1:has-text("Projects")')).toBeVisible({ timeout: 30_000 });
}

/**
 * Fail with an explicit classification rather than an opaque assertion, so an
 * Organization/tenant seam is never mistaken for "Clerk is broken".
 */
async function requireAuthInvariant(
  held: boolean,
  classification: AuthFailureClassification,
  detail: string,
  page: Page,
  observation?: AuthObservation,
): Promise<void> {
  if (held) return;

  const evidence = {
    classification,
    detail,
    facts: await clerkFacts(page),
    currentPath: pathnameOf(page.url()),
    tokenAcquisition: await classifyTokenAcquisition(page),
    apiAuthFailures: observation?.apiAuthFailures ?? [],
    hops: observation ? await observation.hops() : [],
    applicationBearerObserved: observation?.applicationBearerObserved() ?? null,
  };
  throw new Error(
    `${classification}: ${detail}. Structural diagnostics (no values, no tokens):\n` +
      JSON.stringify(evidence, null, 2),
  );
}

// ---------------------------------------------------------------------------
// Step 2 — bounded pre-click stability, then the project-entry transition
// ---------------------------------------------------------------------------

async function buildReport(
  failedAt: string,
  page: Page,
  observation: AuthObservation,
  points: AuthPoint[],
  clickStartedAt: number | null,
): Promise<Record<string, unknown>> {
  const hops = await observation.hops();
  const firstAfterClick =
    clickStartedAt === null ? null : (hops.find((hop) => hop.at >= clickStartedAt) ?? null);

  return {
    classification: classifyAuthFailure({
      hops,
      apiAuthFailures: observation.apiAuthFailures,
      points,
    }),
    failedAt,
    points,
    hops,
    apiAuthFailures: observation.apiAuthFailures,
    tokenAcquisition: await classifyTokenAcquisition(page),
    clickStartedAt,
    firstMainFrameHopAfterClick: firstAfterClick,
    msFromClickToFirstMainFrameNavigation:
      firstAfterClick && clickStartedAt !== null ? firstAfterClick.at - clickStartedAt : null,
  };
}

/** Which invariant broke during the idle window, or null while all hold. */
function stabilityViolation(point: AuthPoint): string | null {
  if (point.currentPath !== "/projects") return `route left /projects (now ${point.currentPath})`;
  if (!point.clerkSessionActive) return "Clerk session stopped being active";
  if (!point.expectedOrganizationActive) return "expected Organization became inactive or absent";
  if (!point.expectedTenantIdActive) return "active Organization stopped carrying the CI tenant id";
  if (point.firstSameOriginApiAuthFailure) {
    const failure = point.firstSameOriginApiAuthFailure;
    return `same-origin API auth failure ${failure.method} ${failure.pathname} -> ${failure.status}`;
  }
  return null;
}

/**
 * Prove the session survives project entry, and LEAVE THE PAGE THERE.
 *
 * The journey continues from this exact state rather than repeating the
 * transition, so the gate is the journey's own first step and cannot drift from
 * it. If continuity breaks it fails in seconds with a classification, never by
 * burning the journey's minutes.
 */
export async function assertProjectEntryContinuity(
  page: Page,
  observation: AuthObservation,
): Promise<void> {
  const points: AuthPoint[] = [];

  // T1 — stable /projects, before any interaction.
  const t1 = await authPoint("T1 stable /projects", page, observation);
  points.push(t1);
  if (!t1.applicationBearerObserved) {
    const report = await buildReport("T1_NO_APPLICATION_BEARER", page, observation, points, null);
    throw new Error(
      "The application never attached a bearer to a same-origin API call, so /projects is " +
        "not proven authenticated; Clerk state alone does not prove it. Structural " +
        `diagnostics (no values, no tokens):\n${JSON.stringify(report, null, 2)}`,
    );
  }

  // Does every invariant survive with NO interaction at all? If not, the click
  // is not the cause and clicking would only muddy the evidence.
  const deadline = Date.now() + STABILITY_WINDOW_MS;
  while (Date.now() < deadline) {
    await page.waitForTimeout(STABILITY_SAMPLE_MS);
    const sample = await authPoint(`idle +${Date.now() - t1.at}ms`, page, observation);
    const violation = stabilityViolation(sample);
    if (violation !== null) {
      points.push(sample);
      const report = await buildReport("PRE_CLICK", page, observation, points, null);
      throw new Error(
        `PRE_CLICK_AUTH_CONTINUITY_FAILURE: ${violation}. The New Project click was NOT ` +
          `performed. Structural diagnostics (no values, no tokens):\n${JSON.stringify(report, null, 2)}`,
      );
    }
  }

  // T2 — immediately before the click.
  points.push(await authPoint("T2 immediately before click", page, observation));

  // Arm observers BEFORE the click, and stamp the clock BEFORE it, so a
  // navigation that happens DURING the click is still attributable to it.
  const input = page.getByTestId("project-name-input");
  const signedOut = page.waitForURL(/\/sign-in/, { timeout: ENTRY_RACE_MS }).then(() => "sign-in");
  const editable = input.waitFor({ state: "visible", timeout: ENTRY_RACE_MS }).then(() => "input");

  const clickStartedAt = Date.now();
  await page.getByRole("button", { name: /new project|create project/i }).first().click();
  points.push(await authPoint("immediately after click", page, observation));

  const outcome = await Promise.race([editable, signedOut]).catch(() => "timeout");

  if (outcome !== "input") {
    // T3 — the first auth/navigation failure event.
    points.push(await authPoint("T3 first failure event", page, observation));
    const report = await buildReport("PROJECT_ENTRY", page, observation, points, clickStartedAt);
    throw new Error(
      `PROJECT_ENTRY_AUTH_CONTINUITY_FAILURE: outcome=${outcome}, expected the project-name ` +
        `input to become visible. Structural diagnostics (no values, no tokens):\n${JSON.stringify(
          report,
          null,
          2,
        )}`,
    );
  }

  await expect(input).toBeEditable({ timeout: 5_000 });
  expect(pathnameOf(page.url()), "must remain on an authenticated route").not.toContain("/sign-in");
}
