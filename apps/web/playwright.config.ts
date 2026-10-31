import { defineConfig, devices } from "@playwright/test";

// Intentionally RED (TDD) specs for features that are not built yet: the S3
// "<id> RED - ..." specs and the review journey declared "Phase: RED". They
// are a backlog, never acceptance evidence, so they run only in "red-backlog".
// Journey 1 declares "Phase: GREEN" (P0) and stays executable.
const redBacklogSpecs = [
  /(^|[\\/])S3-\d+-[^\\/]*\.spec\.ts$/,
  /(^|[\\/])journeys[\\/]journey-2-review\.spec\.ts$/,
];

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3100";
const useManagedWebServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";
const useProductionWebServer = process.env.PLAYWRIGHT_WEBSERVER_MODE === "production";
const webServerCommand = useProductionWebServer
  ? "pnpm start --hostname localhost --port 3100"
  : "pnpm dev --hostname localhost --port 3100 --webpack";

export default defineConfig({
  testDir: "./src/tests/e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: useManagedWebServer
    ? {
        command: webServerCommand,
        url: baseURL,
        reuseExistingServer: false,
        timeout: 120_000,
      }
    : undefined,
  projects: [
    {
      name: "global-setup",
      testMatch: /global\.setup\.ts/,
    },
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
    },
    {
      name: "chromium",
      // The P0b specs sign in live in their own context; restoring a session
      // under them would both mask the variable under investigation and collide
      // with the ticket sign-in.
      testIgnore: [
        /p0b-single-document-health\.spec\.ts/,
        /auth-continuity\.spec\.ts/,
        // Anchored to the file name: matching runs against the absolute path, and a checkout
        // directory may itself contain "pj01-".
        /(^|[\\/])pj01-[^\\/]*\.spec\.ts$/,
        /(^|[\\/])p0c-what-changed\.spec\.ts$/,
        // Own project and Nightly step: a long journey that must not hide the rest of the suite.
        /(^|[\\/])triplet-user-journey\.spec\.ts$/,
        /(^|[\\/])s7-clerk-relogin\.spec\.ts$/,
        // Opt-in integral S1-S8 UAT (own project, own workflow job).
        /(^|[\\/])integral-s1-s8\.spec\.ts$/,
        /(^|[\\/])integral-auth-preflight\.spec\.ts$/,
        /(^|[\\/])prod-acceptance[\\/].*\.spec\.ts$/,
        /pq-hitl-03\.1-revision-readonly\.spec\.ts$/,
        ...redBacklogSpecs,
        // Owned by "visual-regression": its baselines are named for that project.
        /core-pages\.visual\.spec\.ts$/,
      ],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },
    {
      name: "red-backlog",
      testMatch: redBacklogSpecs,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
      metadata: { phase: "red", type: "e2e", description: "Unbuilt-feature TDD backlog; not acceptance" },
    },
    {
      // PJ-01 First Real User Journey. Like P0b: NO storageState — the journey performs the
      // documented Clerk bootstrap itself and needs global-setup for the testing token.
      name: "pj01-acceptance",
      // Keep the canonical journey isolated from focused diagnostics.  Those
      // diagnostics create their own tenant-A projects and must be selected
      // explicitly, never run beside TS-E2E-PJ01-001 under fullyParallel.
      testMatch: [
        /(^|[\\/])pj01-first-user-journey\.spec\.ts$/,
        /(^|[\\/])pj01-tenant-isolation\.spec\.ts$/,
        // ACC-01 S5: UI rejection needs a reason. Same live Clerk login and production runtime as PJ-01.
        /(^|[\\/])pj01-hitl-reject\.spec\.ts$/,
        // ACC-01 S3: a contract awaiting approval is a stated state (not a 404, not a score). Same live Clerk login.
        /(^|[\\/])pj01-contract-pending-approval\.spec\.ts$/,
      ],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "TS-E2E-PJ01-001",
        type: "e2e",
        priority: "p0",
        description: "PJ-01 first real user journey (Login → Create → Upload A → Processing → Health → Evidence → Revision B → What Changed → Current State)",
      },
    },
    {
      // S7 browser signout+fresh-context Clerk authentication. Run only by dedicated UAT.
      name: "s7-clerk-uat",
      testMatch: ["**/s7-clerk-relogin.spec.ts"],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "ACC-01-S7-CLERK-UAT",
        type: "e2e",
        priority: "p0",
        description: "Real Clerk logout and fresh browser login with three typed human-approved source-to-WBS links",
      },
    },
    {
      // Integral ACC-01 S1-S8 UAT: ONE project from the first login to the relogin, two Clerk tenants. Opt-in
      // only (INTEGRAL_UAT=1, set by the integral job of acc01-s2-live-ai-uat.yml); never part of another suite.
      name: "integral-s1-s8",
      testMatch: [/(^|[\\/])integral-s1-s8\.spec\.ts$/],
      use: { ...devices["Desktop Chrome"] },
      // The scenario starts only if both identities authenticated against the local API (JWKS verified).
      dependencies: ["global-setup", "integral-auth-preflight"],
      metadata: {
        suite: "TS-E2E-INTEGRAL-S1S8-001",
        type: "e2e",
        priority: "p0",
        description: "One persisted project S1-S8, two Clerk Development tenants, fail-closed ledger",
      },
    },
    {
      // Authentication preflight of the integral UAT: both Clerk Development identities reach the local API with
      // a real JWT. Read-only (GETs); opt-in (INTEGRAL_UAT=1) and run BEFORE the scenario.
      name: "integral-auth-preflight",
      testMatch: [/(^|[\\/])integral-auth-preflight\.spec\.ts$/],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: { suite: "TS-E2E-INTEGRAL-AUTH-001", type: "e2e", priority: "p0" },
    },
    {
      // Explicit-only focused diagnostics.  They retain their environment
      // guards, but are deliberately outside the canonical PJ-01 selection.
      name: "pj01-focal",
      testMatch: [
        /(^|[\\/])pj01-create-project-observer\.spec\.ts$/,
        /(^|[\\/])pj01-processing-a-focal\.spec\.ts$/,
      ],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
    },
    {
      // P0c What Changed? PRESENTATION acceptance over SEEDED canonical projections
      // (apps/api/scripts/seed_p0c_browser_journey.py). It proves how the UI renders
      // BUSINESS_STATE_CHANGED / NEWLY_DISCOVERED / no-change and unavailable detail, which a
      // user journey cannot produce on demand. It is never evidence for the PJ-01 journey,
      // whose revisions and events must be generated by the application itself.
      name: "p0c-presentation",
      testMatch: [/(^|[\\/])p0c-what-changed\.spec\.ts$/],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "TS-E2E-P0C-PRESENTATION-001",
        type: "e2e",
        priority: "p1",
        description: "What Changed? rendering of seeded canonical P0c projections (not PJ-01 journey evidence)",
      },
    },
    {
      // Canonical P0b acceptance. NO storageState: the journey performs the
      // documented Clerk bootstrap itself, in the same page and context it then
      // gates and continues into. It still needs global-setup, which fetches the
      // Clerk testing token that the development instance requires.
      name: "p0b-acceptance",
      testMatch: [/p0b-single-document-health\.spec\.ts/, /auth-continuity\.spec\.ts/],
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "TS-E2E-P0B-HEALTH-001",
        type: "e2e",
        priority: "p0",
        description: "Single-document Health journey with inline auth gate",
      },
    },
    {
      // Read-only/manual-only qualification identity preflight. It performs a
      // real Clerk sign-in and ordinary projects read, then signs out. No
      // project/document mutation is allowed in this project.
      name: "prod-identity-preflight",
      testMatch: [
        /(^|[\\/])prod-acceptance[\\/]706-production-identity-preflight\.spec\.ts$/,
      ],
      use: {
        ...devices["Desktop Chrome"],
        trace: "off",
        screenshot: "off",
        video: "off",
      },
      metadata: {
        suite: "ISSUE-690-PROD-IDENTITY-PREFLIGHT",
        type: "production-qualification-readonly",
        priority: "p0",
        manualOnly: true,
        description:
          "Real Clerk production auth + synthetic tenant/org binding without product mutation",
      },
    },
    {
      // PQ-HITL-03 / #939: existing qualified production Clerk principal,
      // pre-existing bounded synthetic project/document, GET/UI only.
      // Explicitly selected by protected production qualification workflow.
      name: "prod-pq-hitl-03-readonly",
      testMatch: [
        /(^|[\\/])prod-acceptance[\\/]939-production-revision-readonly\.spec\.ts$/,
      ],
      use: {
        ...devices["Desktop Chrome"],
        trace: "off",
        screenshot: "off",
        video: "off",
      },
      metadata: {
        suite: "PQ-HITL-03-PROD-READONLY",
        type: "production-qualification-readonly",
        manualOnly: true,
        description: "Deployed real Clerk A9/B7 read-only Evidence Viewer and re-login",
      },
    },
    {
      // Manual-only production qualification. No testing-token setup, no
      // storageState and no managed local web server. The caller must set
      // PLAYWRIGHT_SKIP_WEBSERVER=1 and point PLAYWRIGHT_BASE_URL at c2pro.io.
      name: "prod-acceptance",
      testMatch: [/(^|[\\/])prod-acceptance[\\/]706-production-synthetic\.spec\.ts$/],
      use: {
        ...devices["Desktop Chrome"],
        trace: "off",
        screenshot: "off",
        video: "off",
      },
      metadata: {
        suite: "ISSUE-706-PROD-ACCEPTANCE",
        type: "production-qualification",
        priority: "p0",
        manualOnly: true,
        description:
          "Real Clerk production auth -> synthetic project -> upload -> Health/evidence/HITL -> relogin",
      },
    },
    {
      // Manual-only #686 P0c production qualification. Reuses the already
      // accepted synthetic P0b project and mutates only by uploading revision B
      // of the same logical document.
      name: "prod-p0c-acceptance",
      testMatch: [
        /(^|[\\/])prod-acceptance[\\/]686-p0c-production\.spec\.ts$/,
        /(^|[\\/])prod-acceptance[\\/]686-p0c-recovery-production\.spec\.ts$/,
      ],
      use: {
        ...devices["Desktop Chrome"],
        trace: "off",
        screenshot: "off",
        video: "off",
      },
      metadata: {
        suite: "ISSUE-686-P0C-PROD-ACCEPTANCE",
        type: "production-qualification",
        priority: "p0",
        manualOnly: true,
        description:
          "Real Clerk production auth -> accepted P0b document -> revision B -> What Changed -> relogin durability",
      },
    },
    {
      name: "cross-browser-chromium",
      testMatch: /cross-browser-smoke\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
      metadata: {
        task: "TASK-024",
        type: "cross-browser-smoke",
        browser: "chromium",
      },
    },
    {
      name: "cross-browser-firefox",
      testMatch: /cross-browser-smoke\.spec\.ts/,
      use: { ...devices["Desktop Firefox"] },
      metadata: {
        task: "TASK-024",
        type: "cross-browser-smoke",
        browser: "firefox",
      },
    },
    {
      name: "cross-browser-webkit",
      testMatch: /cross-browser-smoke\.spec\.ts/,
      use: { ...devices["Desktop Safari"] },
      metadata: {
        task: "TASK-024",
        type: "cross-browser-smoke",
        browser: "webkit",
      },
    },
    {
      name: "visual-regression",
      testMatch: /core-pages\.visual\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1200 },
        colorScheme: "light",
        locale: "en-US",
        timezoneId: "UTC",
      },
      metadata: {
        task: "TASK-021",
        type: "visual-regression",
        scope: "core-pages",
      },
    },
    {
      // TS-E2E-TRIPLET-001: project → contract → HITL → budget + schedule → coherence →
      // alerts/health/evidence → persistence, on the real local backend. The AI is mocked in
      // the Nightly (C2PRO_AI_MOCK=1); the spec records and declares it. Explicit-only.
      name: "triplet-journey",
      testMatch: /(^|[\\/])triplet-user-journey\.spec\.ts$/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
      metadata: {
        suite: "TS-E2E-TRIPLET-001",
        type: "e2e",
        priority: "p0",
        ai: "mocked-in-nightly",
        description: "Three-document journey; not PQ-HITL-09 S1-S8",
      },
    },
    {
      name: "e2e-j2-weekly-review",
      testMatch: /journey-2-review\.spec\.ts/,
      use: { 
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
      metadata: {
        suite: "TS-E2E-J2-001",
        phase: "red",
        type: "e2e",
        priority: "p0",
        description: "Weekly Project Review Journey",
      },
    },
    {
      name: "e2e-document-analysis-pipeline",
      testMatch: /document-analysis-pipeline\.spec\.ts/,
      use: { 
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
      metadata: {
        suite: "TS-E2E-DAP-001",
        phase: "green",
        type: "e2e",
        priority: "p1",
        task: "TASK-FRT-166",
        description: "Document Analysis Pipeline Journey",
      },
    },
    {
      name: "pq-hitl-03.1-revision-readonly",
      testMatch: /pq-hitl-03\.1-revision-readonly\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global-setup"],
      metadata: {
        suite: "PQ-HITL-03.1",
        type: "e2e",
        priority: "p0",
        description: "Read-only revision evidence, A=9/B=7, unresolved trusted current",
      },
    },
  ],
});
