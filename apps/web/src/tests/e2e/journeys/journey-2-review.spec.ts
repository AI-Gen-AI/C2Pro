/**
 * TS-E2E-J2-001 - Weekly Project Review Journey
 *
 * Test Suite ID: TS-E2E-J2-001
 * Type: E2E Journey Test
 * Priority: P0
 * Phase: RED (Write failing tests first)
 *
 * End-to-end test simulating a project manager performing their weekly
 * project review. Tests viewing coherence scores, reviewing alerts,
 * checking WBS progress, and updating completion status.
 *
 * Run: npx playwright test journey-2-review.spec.ts
 */

import { test, expect } from "@playwright/test";

test.describe("TS-E2E-J2-001: Weekly Project Review Journey", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to login page
    await page.goto("http://localhost:3000/login");
    await expect(page.getByTestId("login-card")).toBeVisible();

    // Login with PM credentials
    await page.getByTestId("email-input").fill("pm@test.com");
    await page.getByTestId("password-input").fill("pmpassword123");

    // Submit form by pressing Enter
    await Promise.all([
      page.waitForURL((url) => url.pathname === "/"),
      page.getByTestId("password-input").press("Enter"),
    ]);

    // Navigate to projects list
    await page.goto("http://localhost:3000/projects");
    await expect(page.getByTestId("projects-list")).toBeVisible();
  });

  test("should navigate to existing project dashboard [TEST-01]", async ({
    page,
  }) => {
    /**
     * RED Phase: PM navigates to existing project from dashboard
     *
     * Expected: Project dashboard with overview stats loads
     */
    // Given: Dashboard with existing projects
    await expect(page.locator('[data-testid="projects-list"]')).toBeVisible();

    // When: PM clicks on a project
    await page.click('[data-testid="project-card-1"]');

    // Then: Should navigate to project dashboard
    await page.waitForURL(/\/projects\/[^/?#]+$/);
    await expect(
      page.locator('[data-testid="project-dashboard"]'),
    ).toBeVisible();

    // Should show project overview stats
    await expect(
      page.locator('[data-testid="coherence-score-card"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="open-alerts-card"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="budget-utilization-card"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="completion-progress-card"]'),
    ).toBeVisible();
  });

  test("should view coherence score and breakdown [TEST-02]", async ({
    page,
  }) => {
    /**
     * RED Phase: PM views coherence score details
     *
     * Expected: Coherence score with category breakdown displayed
     */
    // Navigate to project dashboard
    await page.goto("http://localhost:3000/projects/test-project-id");

    // Should show coherence score
    await expect(
      page.locator('[data-testid="coherence-score-value"]'),
    ).toContainText("78");

    // Click to view breakdown
    await page.click('[data-testid="view-coherence-breakdown-button"]');

    // Should show category breakdown
    await expect(
      page.locator('[data-testid="coherence-breakdown-modal"]'),
    ).toBeVisible();

    // Should show all categories
    await expect(page.locator('text="Scope"')).toBeVisible();
    await expect(page.locator('text="Budget"')).toBeVisible();
    await expect(page.locator('text="Timeline"')).toBeVisible();
    await expect(page.locator('text="Quality"')).toBeVisible();
    await expect(page.locator('text="Legal"')).toBeVisible();

    // Should show individual scores
    await expect(page.locator('[data-testid="scope-score"]')).toContainText(
      "80",
    );
    await expect(page.locator('[data-testid="budget-score"]')).toContainText(
      "62",
    );
  });

  test("should review open alerts [TEST-03]", async ({ page }) => {
    /**
     * RED Phase: PM reviews open alerts
     *
     * Expected: List of open alerts with severity and details
     */
    // Navigate to project alerts page
    await page.goto(
      "http://localhost:3000/projects/test-project-id/alerts",
    );

    // Should show alerts page
    await expect(page.locator('[data-testid="alerts-page"]')).toBeVisible();

    // Should show open alerts section
    await expect(
      page.locator('[data-testid="open-alerts-section"]'),
    ).toBeVisible();

    // Should show alerts with severity indicators
    await expect(page.locator('[data-testid="alert-critical"]')).toBeVisible();
    await expect(page.locator('[data-testid="alert-high"]')).toBeVisible();
    await expect(page.locator('[data-testid="alert-medium"]')).toBeVisible();

    // Should show alert details
    await expect(
      page.locator('text="Contract Penalty Clause Violation Risk"'),
    ).toBeVisible();
    await expect(
      page.locator('text="Critical Path Delay - Foundation Work"'),
    ).toBeVisible();

    // Can filter by severity
    await page.selectOption(
      '[data-testid="alert-severity-filter"]',
      "critical",
    );

    // Should show only critical alerts
    await expect(page.locator('[data-testid="alert-item"]')).toHaveCount(2);
  });

  test("should check WBS progress [TEST-04]", async ({ page }) => {
    /**
     * RED Phase: PM checks WBS item completion status
     *
     * Expected: WBS tree with progress bars and percentages
     */
    // Navigate to WBS page
    await page.goto(
      "http://localhost:3000/projects/test-project-id/wbs",
    );

    // Should show WBS tree
    await expect(page.locator('[data-testid="wbs-tree-view"]')).toBeVisible();

    // Should show root items
    await expect(page.locator('[data-testid="wbs-item-1"]')).toBeVisible();
    await expect(page.locator('text="1 - Project Management"')).toBeVisible();

    // Should show progress bars
    await expect(
      page.locator('[data-testid="wbs-item-1-progress"]'),
    ).toBeVisible();

    // Should show completion percentages
    await expect(
      page.locator('[data-testid="wbs-item-1-completion"]'),
    ).toContainText("75%");

    // Can expand child items
    await page.click('[data-testid="wbs-expand-1"]');

    // Should show child items
    await expect(page.locator('[data-testid="wbs-item-1.1"]')).toBeVisible();
  });

  test("should view budget utilization [TEST-05]", async ({ page }) => {
    /**
     * RED Phase: PM views budget vs actual spending
     *
     * Expected: Budget chart showing utilization and variance
     */
    // Navigate to budget page
    await page.goto(
      "http://localhost:3000/projects/test-project-id/budget",
    );

    // Should show budget page
    await expect(page.locator('[data-testid="budget-page"]')).toBeVisible();

    // Should show total budget
    await expect(page.locator('[data-testid="total-budget"]')).toContainText(
      "€2,500,000",
    );

    // Should show spent amount
    await expect(page.locator('[data-testid="spent-amount"]')).toContainText(
      "€1,550,000",
    );

    // Should show utilization percentage
    await expect(
      page.locator('[data-testid="budget-utilization"]'),
    ).toContainText("62%");

    // Should show budget chart
    await expect(page.locator('[data-testid="budget-chart"]')).toBeVisible();

    // Should show variance
    await expect(page.locator('[data-testid="budget-variance"]')).toContainText(
      "On Track",
    );
  });

  test("should review recent documents [TEST-06]", async ({ page }) => {
    /**
     * RED Phase: PM reviews recently uploaded documents
     *
     * Expected: Document list with timestamps and types
     */
    // Navigate to documents page
    await page.goto(
      "http://localhost:3000/projects/test-project-id/documents",
    );

    // Should show documents page
    await expect(page.locator('[data-testid="documents-page"]')).toBeVisible();

    // Should show recent documents list
    await expect(page.locator('[data-testid="documents-list"]')).toBeVisible();

    // Should show document names
    await expect(
      page.locator('text="Contract Amendment v2.pdf"'),
    ).toBeVisible();
    await expect(page.locator('text="Project Schedule.xlsx"')).toBeVisible();

    // Should show upload timestamps
    await expect(page.locator('[data-testid="document-date"]')).toContainText(
      "2 days ago",
    );

    // Should show document types
    await expect(
      page.locator('[data-testid="document-type-pdf"]'),
    ).toBeVisible();
  });

  test("should update WBS item completion [TEST-07]", async ({ page }) => {
    /**
     * RED Phase: PM updates WBS item completion percentage
     *
     * Expected: Completion updated and saved
     */
    // Navigate to WBS page
    await page.goto(
      "http://localhost:3000/projects/test-project-id/wbs",
    );

    // Find WBS item and click edit
    await page.click('[data-testid="wbs-edit-1.1"]');

    // Should open edit modal
    await expect(page.locator('[data-testid="wbs-edit-modal"]')).toBeVisible();

    // Update completion percentage
    await page.fill('[data-testid="completion-input"]', "85");

    // Add note
    await page.fill(
      '[data-testid="completion-note"]',
      "Foundation work 85% complete - awaiting final inspection",
    );

    // Save changes
    await page.click('[data-testid="save-wbs-changes"]');

    // Modal should close
    await expect(
      page.locator('[data-testid="wbs-edit-modal"]'),
    ).not.toBeVisible();

    // Should show success message
    await expect(page.locator('[data-testid="success-toast"]')).toContainText(
      "Progress updated successfully",
    );

    // Updated completion should be visible
    await expect(
      page.locator('[data-testid="wbs-item-1.1-completion"]'),
    ).toContainText("85%");
  });

  test("should mark alert as resolved [TEST-08]", async ({ page }) => {
    /**
     * RED Phase: PM marks an alert as resolved
     *
     * Expected: Alert moved to resolved list
     */
    // Navigate to alerts page
    await page.goto(
      "http://localhost:3000/projects/test-project-id/alerts",
    );

    // Find alert and click resolve
    await page.click(
      '[data-testid="alert-item-1"] [data-testid="resolve-button"]',
    );

    // Should show resolution dialog
    await expect(
      page.locator('[data-testid="resolve-alert-dialog"]'),
    ).toBeVisible();

    // Select resolution type
    await page.selectOption('[data-testid="resolution-type"]', "mitigated");

    // Add resolution notes
    await page.fill(
      '[data-testid="resolution-notes"]',
      "Issue resolved - contractor provided updated schedule",
    );

    // Confirm resolution
    await page.click('[data-testid="confirm-resolve"]');

    // Dialog should close
    await expect(
      page.locator('[data-testid="resolve-alert-dialog"]'),
    ).not.toBeVisible();

    // Should show success message
    await expect(page.locator('[data-testid="success-toast"]')).toContainText(
      "Alert resolved",
    );

    // Alert should move to resolved section
    await page.click('[data-testid="resolved-alerts-tab"]');
    await expect(
      page.locator('[data-testid="resolved-alerts-section"]'),
    ).toContainText("Contract Penalty Clause Violation Risk");
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================
