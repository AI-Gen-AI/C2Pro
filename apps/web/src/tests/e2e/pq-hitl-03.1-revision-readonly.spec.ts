import { test, expect } from "@playwright/test";
import { establishAuthenticatedSession, openProjects } from "./support/p0b-auth";

const OTHER_TENANT_PROJECT_ID = "00000000-0000-0000-0000-00000000c304";
const OTHER_TENANT_DOCUMENT_ID = "00000000-0000-0000-0000-00000000d404";
const SAME_TENANT_PROJECT_ID = "00000000-0000-0000-0000-00000000c305";
const PROJECT_ID = "00000000-0000-0000-0000-00000000c303";
const DOCUMENT_ID = "00000000-0000-0000-0000-00000000d401";

test.describe("PQ-HITL-03.1 revision read-only evidence", () => {
  test.describe.configure({ timeout: 120_000 }); // Bounded real Clerk setup + re-login.
  test.beforeEach(async ({ page }) => {
    await establishAuthenticatedSession(page);
  });

  test("revision history shows 9 and 7 clauses, B proposed not trusted, no trusted current", async ({ page }) => {
    await openProjects(page);
    await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);

    const panel = page.getByTestId("revision-history-readonly");
    await expect(panel).toBeVisible();

    await expect(panel.getByText(/No trusted-current revision is available/i)).toBeVisible();

    const revButtons = page.getByRole("button", { name: /^Revision \d+ —/ });
    await expect(revButtons).toHaveCount(2);

    await page.getByRole("button", { name: /^Revision 1 —/ }).click();
    const preview = page.getByTestId("revision-specific-preview");
    await expect(preview).toBeVisible();
    await expect(preview.getByText(/9 stored clauses in this selected revision/i)).toBeVisible();
    await expect(preview.getByText(/Proposed — not trusted/i)).toBeHidden();
    // Synthetic revision panel only: do not capture Clerk identity or contract source.
    await panel.screenshot({ path: test.info().outputPath("pq-hitl-031-rev-a.png") });

    await page.getByRole("button", { name: /^Revision 2 —/ }).click();
    await expect(preview.getByText(/7 stored clauses in this selected revision/i)).toBeVisible();
    await expect(preview.getByText(/Proposed — not trusted/i)).toBeVisible();

    await expect(preview.getByRole("listitem")).toHaveCount(7);
    await panel.screenshot({ path: test.info().outputPath("pq-hitl-031-rev-b.png") });
  });

  test("re-login stability preserves revision states", async ({ page }) => {
    await openProjects(page);
    await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
    const panel = page.getByTestId("revision-history-readonly");
    await expect(panel.getByText(/No trusted-current revision is available/i)).toBeVisible();

    await page.getByRole("button", { name: /User menu/i }).click();
    await page.getByRole("menuitem", { name: /Sign out/i }).click();
    await expect(page.getByRole("heading", { name: "Sign in to C2Pro" })).toBeVisible();

    await establishAuthenticatedSession(page);
    await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
    await expect(panel.getByText(/No trusted-current revision is available/i)).toBeVisible();
    await page.getByRole("button", { name: /^Revision 1 —/ }).click();
    const preview = page.getByTestId("revision-specific-preview");
    await expect(preview.getByText(/9 stored clauses in this selected revision/i)).toBeVisible();

    // Re-login must preserve the complete A/B inventory and B's non-trusted state.
    const revisions = page.getByRole("button", { name: /^Revision [0-9]+ —/ });
    await expect(revisions).toHaveCount(2);
    await page.getByRole("button", { name: /^Revision 2 —/ }).click();
    await expect(preview.getByText(/7 stored clauses in this selected revision/i)).toBeVisible();
    await expect(preview.getByText(/Proposed — not trusted/i)).toBeVisible();
    await expect(preview.getByRole("listitem")).toHaveCount(7);
  });

  test("unknown project GET is denied without exposing revision data", async ({ page }) => {
    const unknownProjectId = "00000000-0000-0000-0000-ffffffffffff";
    const projectResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.startsWith("/api/") &&
        new URL(response.url()).pathname.endsWith("/projects/" + unknownProjectId) &&
        response.request().method() === "GET",
    );
    await page.goto("/projects/" + unknownProjectId + "/evidence?documentId=" + DOCUMENT_ID);
    expect((await projectResponse).status()).toBe(404);
    await expect(page.getByTestId("revision-history-readonly")).toHaveCount(0);
  });

  test("real tenant B project and document are hidden from tenant A Clerk user", async ({ page }) => {
    // The project route's 404 cannot prove document-scoped RLS. Call BOTH APIs
    // using the actual authenticated Clerk session from the browser; no token
    // or tenant identifier may leave this evaluate callback or enter artifacts.
    const documentStatuses = await page.evaluate(async (documentId) => {
      const token = await window.Clerk?.session?.getToken();
      const tenantId = window.Clerk?.organization?.publicMetadata?.tenant_id;
      if (!token || typeof tenantId !== "string") {
        throw new Error("PQ031_AUTH_CONTEXT_MISSING");
      }
      const headers = { Authorization: `Bearer ${token}`, "X-Tenant-ID": tenantId };
      const responses = await Promise.all([
        fetch(`/api/v1/documents/${documentId}/revisions`, { headers, redirect: "manual" }),
        fetch(`/api/v1/documents/${documentId}/entities`, { headers, redirect: "manual" }),
      ]);
      return responses.map((response) => response.status);
    }, OTHER_TENANT_DOCUMENT_ID);
    expect(documentStatuses).toEqual([404, 404]);

    const projectResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.startsWith("/api/") &&
        new URL(response.url()).pathname.endsWith("/projects/" + OTHER_TENANT_PROJECT_ID) &&
        response.request().method() === "GET",
    );
    await page.goto("/projects/" + OTHER_TENANT_PROJECT_ID + "/evidence?documentId=" + OTHER_TENANT_DOCUMENT_ID);
    expect((await projectResponse).status()).toBe(404);
    await expect(page.getByTestId("revision-history-readonly")).toHaveCount(0);
    await expect(page.getByText("tenant-b-private.pdf")).toHaveCount(0);
  });

  test("real same-tenant project excludes document belonging to another project", async ({ page }) => {
    const projectResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.startsWith("/api/") &&
        new URL(response.url()).pathname.endsWith("/projects/" + SAME_TENANT_PROJECT_ID) &&
        response.request().method() === "GET",
    );
    await page.goto("/projects/" + SAME_TENANT_PROJECT_ID + "/evidence?documentId=" + DOCUMENT_ID);
    expect((await projectResponse).status()).toBe(200);
    await expect(page.getByTestId("evidence-link-unavailable")).toBeVisible();
    await expect(page.getByTestId("revision-history-readonly")).toHaveCount(0);
    await expect(page.getByText(/9 stored clauses in this selected revision/i)).toHaveCount(0);
  });
});


// PQ-HITL-09/#945: exercise the real HTTP boundary WITHOUT a Clerk session.
// This is a negative browser/API test, not a substitute for the second tenant's
// independently authenticated B-to-A read that remains a separate QA residual.
test.describe("PQ-HITL-09 anonymous document isolation", () => {
  test("anonymous client cannot read either synthetic tenant's revisions or entities", async ({ browser }) => {
    const context = await browser.newContext({
      baseURL: test.info().project.use.baseURL,
      // Override any suite storageState: an explicit empty jar is essential.
      storageState: { cookies: [], origins: [] },
    });
    try {
      const paths = [
        "/api/v1/documents/" + DOCUMENT_ID + "/revisions",
        "/api/v1/documents/" + DOCUMENT_ID + "/entities",
        "/api/v1/documents/" + OTHER_TENANT_DOCUMENT_ID + "/revisions",
        "/api/v1/documents/" + OTHER_TENANT_DOCUMENT_ID + "/entities",
      ];
      for (const path of paths) {
        const response = await context.request.get(path, { maxRedirects: 0 });
        const status = response.status();
        const unauthorized = [401, 403, 404].includes(status);
        const authRedirect = [302, 303, 307, 308].includes(status) &&
          /sign-in|sign_in|login|clerk/i.test(response.headers()["location"] ?? "");
        expect(
          unauthorized || authRedirect,
          "Anonymous access unexpectedly permitted or failed unclearly: " + path + " -> " + status,
        ).toBe(true);

        // No response payload may disclose seeded tenant/revision content.
        const body = await response.text();
        expect(body).not.toContain("tenant-b-private.pdf");
        expect(body).not.toContain("9 stored clauses in this selected revision");
        expect(body).not.toContain("7 stored clauses in this selected revision");
      }
    } finally {
      await context.close();
    }
  });
});
