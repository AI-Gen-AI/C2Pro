import { test, expect } from "@playwright/test";
import { establishAuthenticatedSession, openProjects } from "./support/p0b-auth";

const OTHER_TENANT_PROJECT_ID = "00000000-0000-0000-0000-00000000c304";
const OTHER_TENANT_DOCUMENT_ID = "00000000-0000-0000-0000-00000000d404";
const SAME_TENANT_PROJECT_ID = "00000000-0000-0000-0000-00000000c305";
const PROJECT_ID = "00000000-0000-0000-0000-00000000c303";
const DOCUMENT_ID = "00000000-0000-0000-0000-00000000d401";

test.describe("PQ-HITL-03.1 revision read-only evidence", () => {
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

    await page.getByRole("button", { name: /^Revision 2 —/ }).click();
    await expect(preview.getByText(/7 stored clauses in this selected revision/i)).toBeVisible();
    await expect(preview.getByText(/Proposed — not trusted/i)).toBeVisible();

    await expect(preview.getByRole("listitem")).toHaveCount(7);
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
