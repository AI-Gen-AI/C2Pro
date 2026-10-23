/**
 * TS-E2E-J1-001 — current three-step project creation wizard.
 *
 * Real browser and authenticated backend. No route mocking, no fake success,
 * and no assertions for retired contract/clauses/WBS creation steps.
 */
import { expect, test } from "@playwright/test";
import { openProjects } from "../support/p0b-auth";

const projectName = `Journey 1 Acceptance ${Date.now()}`;

test.describe("TS-E2E-J1-001: first project setup", () => {
  test("creates a project through the current three-step wizard", async ({ page }) => {
    // The chromium project depends on auth.setup.ts and restores its Clerk session.
    // Re-signing into an already active session fails with Clerk "already signed in".
    await openProjects(page);
    await page.goto("/projects/new");
    await expect(page).toHaveURL(/\/projects\?create=1/, { timeout: 30_000 });

    const wizard = page.getByRole("dialog", { name: "Create project" });
    await expect(wizard).toBeVisible();
    await expect(wizard).toContainText("Step 1 of 3");
    await wizard.getByTestId("project-name-input").fill(projectName);
    await wizard.getByTestId("project-code-input").fill("JOURNEY1");
    await wizard.getByTestId("project-type-select").selectOption("building");
    await wizard.getByRole("button", { name: "Next step" }).click();

    await expect(wizard).toContainText("Step 2 of 3");
    await wizard.getByTestId("client-name-input").fill("Journey 1 Test Client");
    await wizard.getByTestId("project-description-input").fill("Real project wizard acceptance");
    await wizard.getByTestId("currency-select").selectOption("EUR");
    await wizard.getByRole("button", { name: "Review project" }).click();

    await expect(wizard).toContainText("Step 3 of 3");
    await expect(wizard.getByTestId("review-name")).toHaveText(projectName);
    await expect(wizard.getByTestId("review-client")).toHaveText("Journey 1 Test Client");
    await expect(wizard.getByTestId("review-currency")).toHaveText("EUR");
    await wizard.getByRole("button", { name: "Create project", exact: true }).click();

    await expect(page).toHaveURL(/\/projects\/[^/?#]+\/documents(?:[?#].*)?$/, { timeout: 30_000 });
    await expect(wizard).not.toBeVisible();
  });
});
