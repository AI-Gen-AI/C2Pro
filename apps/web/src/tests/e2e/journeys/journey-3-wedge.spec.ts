/**
 * Test Suite ID: TS-E2E-WEDGE-003
 * Coverage: E2E-W1..W5 Level-1 wedge journey.
 */
import { expect, test, type Page } from "@playwright/test";

const liveProjectId = "00000000-0000-0000-0000-00000000c303";
const projectId = liveProjectId;
const projectName = "Wedge Gate Pilot";
const liveContractId = "00000000-0000-0000-0000-00000000d401";
const liveReviewItemId = "00000000-0000-0000-0000-00000000f601";
const liveReviewRowId = "00000000-0000-0000-0000-00000000f701";
const clerkE2eUserId = process.env.CLERK_E2E_USER_ID ?? "user_3H0l5NCcPYLnfWokjdm2D8m3iGR";

const documents = [
  {
    id: "doc-contract",
    filename: "baseline-contract.pdf",
    document_type: "contract",
    status: "parsed",
    file_size_bytes: 420_000,
    uploaded_at: "2026-07-10T08:00:00Z",
  },
  {
    id: "doc-budget",
    filename: "validated-budget.xlsx",
    document_type: "budget",
    status: "parsed",
    file_size_bytes: 260_000,
    uploaded_at: "2026-07-10T08:05:00Z",
  },
  {
    id: "doc-schedule",
    filename: "approved-schedule.xlsx",
    document_type: "schedule",
    status: "parsed",
    file_size_bytes: 310_000,
    uploaded_at: "2026-07-10T08:10:00Z",
  },
];

async function installWedgeRoutes(page: Page) {
  let approved = false;

  await page.route(`**/api/projects/${projectId}`, (route) =>
    route.fulfill({
      json: {
        id: projectId,
        name: projectName,
        code: "WEDGE-3",
        description: "Deterministic wedge journey fixture",
        project_type: "epc",
        status: "active",
        estimated_budget: 654_000_000,
        currency: "EUR",
        version: 1,
      },
    }),
  );

  await page.route(`**/api/projects/${projectId}/documents`, async (route) => {
    if (route.request().method() === "POST") {
      const form = await route.request().postDataBuffer();
      expect(form?.byteLength ?? 0).toBeGreaterThan(0);
      return route.fulfill({
        status: 201,
        json: { id: "doc-uploaded", task_id: "task-wedge-upload" },
      });
    }

    return route.fulfill({
      json: {
        items: documents,
        total_count: documents.length,
        skip: 0,
        limit: 50,
      },
    });
  });

  await page.route("**/api/coherence/dashboard/**", (route) =>
    route.fulfill({
      json: {
        project_id: projectId,
        tenant_id: "tenant-wedge",
        coherence_score: 82,
        global_score: 82,
        sub_scores: {
          SCOPE: 84,
          BUDGET: 78,
          QUALITY: 86,
          TECHNICAL: 80,
          LEGAL: 88,
          TIME: 76,
        },
        weights_used: {
          SCOPE: 0.17,
          BUDGET: 0.17,
          QUALITY: 0.16,
          TECHNICAL: 0.16,
          LEGAL: 0.17,
          TIME: 0.17,
        },
        alert_count: 1,
        document_count: 3,
        methodology_version: "v1",
        score_version: "coherence-v1",
        score_reason: null,
        score_missing_dimensions: [],
        last_updated: "2026-07-10T09:00:00Z",
      },
    }),
  );

  await page.route("**/api/coherence/evaluate", (route) =>
    route.fulfill({
      status: 202,
      json: { project_id: projectId, status: "queued" },
    }),
  );

  await page.route(`**/api/alerts/projects/${projectId}**`, (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "alert-wedge-1",
            title: "Budget deviation has supporting evidence",
            severity: "medium",
            status: approved ? "approved" : "open",
            created_at: "2026-07-10T09:15:00Z",
            document_id: "doc-contract",
          },
        ],
        total: 1,
      },
    }),
  );

  await page.route("**/api/hitl/queue**", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            item_id: "review-wedge-1",
            row_id: "review-row-wedge-1",
            item_type: "alert",
            current_status: approved ? "APPROVED" : "PENDING_REVIEW_REQUIRED",
            confidence: 0.88,
            impact_level: "MEDIUM",
            approved_by: approved ? "wedge.reviewer@example.com" : null,
            approved_at: approved ? "2026-07-10T09:30:00Z" : null,
            sla_due_date: "2026-07-17T09:30:00Z",
            created_at: "2026-07-10T09:20:00Z",
            item_data: {
              summary: "Budget deviation has supporting evidence",
              document_id: "doc-contract",
              evidence_url: `/projects/${projectId}/evidence?documentId=doc-contract`,
            },
          },
        ],
        total: 1,
      },
    }),
  );

  await page.route("**/api/hitl/queue/review-row-wedge-1/approve", (route) => {
    approved = true;
    return route.fulfill({
      json: {
        item_id: "review-wedge-1",
        row_id: "review-row-wedge-1",
        item_type: "alert",
        current_status: "APPROVED",
        confidence: 0.88,
        impact_level: "MEDIUM",
        approved_by: "wedge.reviewer@example.com",
        approved_at: "2026-07-10T09:30:00Z",
        item_data: { summary: "Budget deviation has supporting evidence" },
      },
    });
  });

  await page.route("**/api/documents/doc-contract/**", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
      },
    }),
  );
}

async function waitForAuthenticatedSession(page: Page) {
  const projectsResponse = page.waitForResponse(
    (response) =>
      ["/api/projects", "/api/v1/projects"].includes(
        new URL(response.url()).pathname,
      ) &&
      response.status() === 200,
  );

  await gotoStable(page, "/projects");
  await projectsResponse;
}

/**
 * goto() that survives a navigation still in flight from the previous step
 * (`net::ERR_ABORTED`): the Next.js app can issue a client-side redirect right
 * after /projects settles. Only that abort is retried; any other failure surfaces.
 */
async function expectDataLoaded(
  page: Page,
  ids: { ready: string; loading: string; error: string },
): Promise<void> {
  try {
    await expect(page.getByTestId(ids.ready)).toBeVisible({ timeout: 30_000 });
  } catch {
    const backendError = await page.getByTestId(ids.error).innerText({ timeout: 1_000 }).catch(() => null);
    const stillLoading = (await page.getByTestId(ids.loading).count()) > 0;
    throw new Error(
      `${ids.ready} not shown after 30 s: ` +
        (backendError ? `the page rendered a backend error: ${backendError}` : stillLoading ? "still loading" : "neither loading nor error rendered"),
    );
  }
}

async function gotoStable(page: Page, url: string) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await page.goto(url);
      return;
    } catch (error) {
      if (!/ERR_ABORTED/.test(String(error)) || attempt === 2) throw error;
      await page.waitForLoadState("domcontentloaded");
    }
  }
}

async function getSessionSubject(page: Page): Promise<string | null> {
  // The Next.js app can still be navigating (RSC redirect, Clerk hydration) right
  // after goto(); evaluating in a document that is being replaced throws
  // "Execution context was destroyed". Retry until a stable document answers.
  let lastError: unknown;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await page.waitForLoadState("domcontentloaded");
      await page.waitForFunction(() => window.Clerk?.loaded === true, undefined, {
        timeout: 30_000,
      });
      return await page.evaluate(async () => {
        const token = await window.Clerk?.session?.getToken();
        if (!token) return null;

        const payload = token.split(".")[1];
        if (!payload) return null;

        const normalizedPayload = payload.replace(/-/g, "+").replace(/_/g, "/");
        const subject = (JSON.parse(atob(normalizedPayload)) as { sub?: unknown }).sub;
        return typeof subject === "string" ? subject : null;
      });
    } catch (error) {
      lastError = error;
      if (!/Execution context was destroyed|navigation/i.test(String(error))) throw error;
      await page.waitForTimeout(500);
    }
  }
  throw lastError;
}

// The chromium project restores the authenticated Clerk session produced by
// auth.setup.ts. Signing out and signing in again here only raced that session
// (and required a credential literal in the repository), so assert the restored
// identity instead.
test.beforeEach(async ({ page }) => {
  await waitForAuthenticatedSession(page);

  const sessionSubject = await getSessionSubject(page);
  expect(sessionSubject).toBe(clerkE2eUserId);
});

test("E2E-W1..W5 typed triplet to report export", async ({ page }) => {
  // First-compiled routes (documents, coherence, evidence, review, report) under the dev server.
  test.setTimeout(120_000);
  await installWedgeRoutes(page);

  await gotoStable(page, `/projects/${projectId}/documents`);
  await expect(page.getByTestId("documents-page")).toBeVisible();
  await expect(page.getByText(/triplet complete/i)).toBeVisible();
  // The rows render after the documents request settles (the checklist above comes first).
  await expect(
    page.getByText("baseline-contract.pdf"),
    "the documents table must list the mocked contract once its request settles",
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("validated-budget.xlsx")).toBeVisible();
  await expect(page.getByText("approved-schedule.xlsx")).toBeVisible();

  await page.getByRole("button", { name: /evaluate coherence/i }).click();

  await gotoStable(page, `/projects/${projectId}/coherence?cohV1Scenario=full-triplet`);
  await expect(page.getByRole("heading", { name: "Coherence Dashboard" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Coherence Score: 82/100, Good" })).toBeVisible();

  await gotoStable(page, `/projects/${projectId}/documents`);
  await expect(page.getByRole("link", { name: "baseline-contract.pdf" })).toHaveAttribute(
    "href",
    `/projects/${projectId}/evidence?documentId=doc-contract`,
  );

  await gotoStable(page, `/projects/${projectId}/review`);
  await expectDataLoaded(page, { ready: "review-page", loading: "review-loading", error: "review-error" });
  await expect(page.getByText(/budget deviation has supporting evidence/i)).toBeVisible();
  await page.getByTestId("approve-review-wedge-1").click();
  await expect(page.getByRole("dialog", { name: /approve review item/i })).toBeVisible();
  await page.getByRole("button", { name: /confirm approve/i }).click();
  await expect(page.getByTestId("stat-approved")).toContainText("1");

  // The Report tab defaults to Current State (P0d slice 8); the Audit Report view is
  // reached only via ?mode=audit, matching what a user gets from clicking "Audit export".
  await gotoStable(page, `/projects/${projectId}/report?mode=audit`);
  await expect(page.getByRole("heading", { name: /audit report/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: projectName }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /download json/i })).toBeEnabled();
});

test("E2E-W3..W5 @real-backend validates the seeded wedge", async ({ page }) => {
  // Five real routes (first-time Next.js compilation in CI), a real HITL approval
  // and the audit report: far beyond the 30 s default. An explicit budget keeps
  // a genuine failure a locator failure instead of a masked global timeout.
  test.setTimeout(180_000);
  // The app's own data request for the list (fetch/XHR), not the page navigation, which matches the
  // same path and answers with HTML long before any document is loaded.
  const documentsListResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      ["fetch", "xhr"].includes(response.request().resourceType()) &&
      new URL(response.url()).pathname.replace(/\/$/, "").endsWith(`/projects/${liveProjectId}/documents`),
    { timeout: 60_000 },
  );
  await gotoStable(page, `/projects/${liveProjectId}/documents`);
  await expect(page.getByTestId("documents-page")).toBeVisible();
  // Wait for the list the app requested before judging what it rendered; surface what the backend
  // answered when the seeded names are not rendered.
  const listed = await documentsListResponse.then(
    async (response) => `${response.status()} ${(await response.text()).slice(0, 600)}`,
    () => "no documents list response observed",
  );
  await expect(
    page.getByText("baseline-contract.pdf"),
    `documents list answered: ${listed}`,
  ).toBeVisible();
  await expect(page.getByText("validated-budget.xlsx")).toBeVisible();
  await expect(page.getByText("approved-schedule.xlsx")).toBeVisible();

  await expect(page.getByRole("link", { name: "baseline-contract.pdf" })).toHaveAttribute(
    "href",
    `/projects/${liveProjectId}/evidence?documentId=${liveContractId}`,
  );

  await gotoStable(page, `/projects/${liveProjectId}/review`);
  // The page renders `review-page` only after its queue request settles (`review-loading` before,
  // `review-error` on failure): wait for that state and say which one it is stuck in.
  await expectDataLoaded(page, { ready: "review-page", loading: "review-loading", error: "review-error" });
  await expect(page.getByTestId(`review-item-${liveReviewItemId}`)).toBeVisible();

  const approveResponse = page.waitForResponse((response) =>
    response.request().method() === "POST" &&
    response.url().includes(`/api/hitl/queue/${liveReviewRowId}/approve`),
  );
  await page.getByTestId(`approve-${liveReviewItemId}`).click();
  await expect(page.getByRole("dialog", { name: /approve review item/i })).toBeVisible();
  await page.getByRole("button", { name: /confirm approve/i }).click();
  await expect((await approveResponse).status()).toBe(200);
  await expect(page.getByTestId("stat-approved")).toContainText("1");

  // The Report tab defaults to Current State (P0d slice 8); the Audit Report view is
  // reached only via ?mode=audit, matching what a user gets from clicking "Audit export".
  await gotoStable(page, `/projects/${liveProjectId}/report?mode=audit`);
  // The audit report composes five API reads on a route the dev server compiles on first
  // visit: give it an explicit, bounded budget (the default 5 s failed intermittently).
  const reportReady = { timeout: 30_000 };
  await expect(page.getByRole("heading", { name: /audit report/i })).toBeVisible(reportReady);
  await expect(page.getByRole("heading", { name: projectName }).first()).toBeVisible(reportReady);
  await expect(page.getByText("HITL decisions")).toBeVisible(reportReady);
  await expect(page.getByRole("button", { name: /download json/i })).toBeEnabled(reportReady);
});
