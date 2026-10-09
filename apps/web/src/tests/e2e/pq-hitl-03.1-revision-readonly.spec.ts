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

    // Wait for revision history panel
    const panel = page.getByTestId("revision-history-readonly");
    await expect(panel).toBeVisible();

    // No trusted current message
    await expect(page.getByText(/No trusted-current revision is available/i)).toBeVisible();

    // Revision buttons
    const revButtons = page.getByRole("button", { name: /Revision \d+ —/ });
    await expect(revButtons).toHaveCount(2);

    // Select revision 1
    await page.getByRole("button", { name: /Revision 1 —/ }).click();
    const preview = page.getByTestId("revision-specific-preview");
    await expect(preview).toBeVisible();
    await expect(page.getByText(/9 stored clauses in this selected revision/i)).toBeVisible();
    await expect(page.getByText(/Proposed — not trusted/i)).toBeHidden();

    // Select revision 2
    await page.getByRole("button", { name: /Revision 2 —/ }).click();
    await expect(page.getByText(/7 stored clauses in this selected revision/i)).toBeVisible();
    await expect(page.getByText(/Proposed — not trusted/i)).toBeVisible();

    // Evidence rows exist
    await expect(preview.getByRole("listitem")).toHaveCount(7);
  });

  test("re-login stability preserves revision states", async ({ page }) => {
    await openProjects(page);
    await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
    await expect(page.getByText(/No trusted-current revision is available/i)).toBeVisible();

    // Sign out via UI
    await page.getByRole("button", { name: /User menu/i }).click();
    await page.getByRole("menuitem", { name: /Sign out/i }).click();
    await expect(page.getByText(/Sign in/i)).toBeVisible();

    // Re-authenticate
    await establishAuthenticatedSession(page);
    await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
    // Re-select revision 1 explicitly
    await page.getByRole("button", { name: /Revision 1 —/ }).click();
    await expect(page.getByText(/9 stored clauses in this selected revision/i)).toBeVisible();
  });

  test("negative access to other tenant returns no data", async ({ page }) => {
    // Wrong project id for same tenant – should be empty / not found
    await page.goto(`/projects/00000000-0000-0000-0000-ffffffffffff/evidence?documentId=${DOCUMENT_ID}`);
    const errorText = page.getByText(/Revision history could not be loaded/i);
    const forbidden = page.getByRole("heading", { name: /403|Forbidden|Not found/i });
    await expect(errorText.or(forbidden)).toBeVisible();
  });
});
