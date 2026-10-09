import { test, expect } from "@playwright/test";
import { establishAuthenticatedSession, openProjects } from "./support/p0b-auth";

const TENANT_ID = "00000000-0000-0000-0000-00000000a113";
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
    await expect(page.getByText(/Sign in/i)).toBeVisible();

    await establishAuthenticatedSession(page);
    await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
    await expect(panel.getByText(/No trusted-current revision is available/i)).toBeVisible();
    await page.getByRole("button", { name: /^Revision 1 —/ }).click();
    const preview = page.getByTestId("revision-specific-preview");
    await expect(preview.getByText(/9 stored clauses in this selected revision/i)).toBeVisible();
  });

  test("negative access to unknown project returns no data", async ({ page }) => {
    const unknownProjectId = "00000000-0000-0000-0000-ffffffffffff";
    await page.goto(`/projects/${unknownProjectId}/evidence?documentId=${DOCUMENT_ID}`);
    const errorText = page.getByText(/Revision history could not be loaded/i);
    const notFound = page.getByRole("heading", { name: /Not found|404/i });
    const forbidden = page.getByText(/Forbidden|403/i);
    await expect(errorText.or(notFound).or(forbidden)).toBeVisible();
  });

  test("negative access to wrong tenant project is forbidden", async ({ page }) => {
    const otherTenantProjectId = "00000000-0000-0000-0000-00000000c304";
    await page.goto(`/projects/${otherTenantProjectId}/evidence?documentId=${DOCUMENT_ID}`);
    const notFound = page.getByRole("heading", { name: /Not found|404/i });
    const forbidden = page.getByText(/Forbidden|403/i);
    await expect(notFound.or(forbidden)).toBeVisible();
  });
});
