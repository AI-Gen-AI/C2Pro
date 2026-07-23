/**
 * TS-E2E-J1-001 - First-Time Project Setup Journey
 *
 * Test Suite ID: TS-E2E-J1-001
 * Type: E2E Journey Test
 * Priority: P0
 * Phase: GREEN (All tests passing - Implementation complete)
 *
 * End-to-end test simulating a first-time user creating their first project.
 * Tests the complete flow from login to project dashboard.
 *
 * Run: pnpm exec playwright test journey-1-setup.spec.ts
 */

import { test, expect } from "@playwright/test";
import { setupClerkTestingToken } from "@clerk/testing/playwright";

test.describe("TS-E2E-J1-001: First-Time Project Setup Journey", () => {
  test.beforeEach(async ({ page }) => {
    // Setup Clerk testing token to bypass bot detection
    await setupClerkTestingToken({ page });
    
    // Navigate to app home (authenticated via storageState)
    await page.goto("/");
  });

  test("should navigate to project creation from empty dashboard [TEST-01]", async ({
    page,
  }) => {
    /**
     * GREEN Phase: User sees empty dashboard and clicks create project
     *
     * Expected: Navigate to project creation form
     */
    // Given: Empty dashboard with no projects
    await expect(page.locator('[data-testid="empty-dashboard"]')).toBeVisible();
    await expect(page.locator('text="No projects yet"')).toBeVisible();

    // When: User clicks "Create First Project" button
    await page.click('[data-testid="create-first-project-button"]');

    // Then: Should navigate to project creation form
    await expect(page).toHaveURL(/.*\/projects\/new/);
    await expect(
      page.locator('[data-testid="project-creation-form"]'),
    ).toBeVisible();
    await expect(
      page.locator('h1:has-text("Create New Project")'),
    ).toBeVisible();
  });

  test("should fill project basic information [TEST-02]", async ({ page }) => {
    /**
     * RED Phase: User fills project name, client, and dates
     *
     * Expected: Form accepts and validates all inputs
     */
    // Navigate to project creation
    await page.goto("http://localhost:3000/projects/new");

    // Fill project name
    await page.fill(
      '[data-testid="project-name-input"]',
      "Commercial Building Renovation",
    );

    // Fill client name
    await page.fill(
      '[data-testid="client-name-input"]',
      "ABC Construction Corp",
    );

    // Fill project description
    await page.fill(
      '[data-testid="project-description-input"]',
      "Complete renovation of 5-story commercial building including HVAC, electrical, and structural updates",
    );

    // Select start date
    await page.fill('[data-testid="start-date-input"]', "2025-06-01");

    // Select end date
    await page.fill('[data-testid="end-date-input"]', "2025-12-31");

    // Select currency
    await page.selectOption('[data-testid="currency-select"]', "EUR");

    // Click next to proceed
    await page.click('[data-testid="project-info-next-button"]');

    // Should proceed to contract upload step
    await expect(
      page.locator('[data-testid="contract-upload-step"]'),
    ).toBeVisible();
  });

  test("should upload contract document [TEST-03]", async ({ page }) => {
    /**
     * RED Phase: User uploads contract PDF document
     *
     * Expected: Document uploaded and processed
     */
    // Navigate to contract upload step
    await page.goto("http://localhost:3000/projects/new?step=contract");

    // Upload contract file
    const fileInput = page.locator('[data-testid="contract-file-input"]');
    await fileInput.setInputFiles("./test-data/sample-contract.pdf");

    // Should show upload progress
    await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();

    // Wait for upload to complete
    await expect(page.locator('[data-testid="upload-complete"]')).toBeVisible({
      timeout: 30000,
    });

    // Should show file name
    await expect(page.locator('text="sample-contract.pdf"')).toBeVisible();

    // Click next to proceed to extraction
    await page.click('[data-testid="upload-next-button"]');

    // Should show extraction progress
    await expect(
      page.locator('[data-testid="extraction-progress"]'),
    ).toBeVisible();
  });

  test("should display AI-extracted clauses [TEST-04]", async ({ page }) => {
    /**
     * RED Phase: System extracts contract clauses using AI
     *
     * Expected: Extracted clauses displayed in preview
     */
    // Navigate to clause review step (simulating extraction complete)
    await page.goto("http://localhost:3000/projects/new?step=clauses");

    // Should show extracted clauses section
    await expect(
      page.locator('[data-testid="extracted-clauses-section"]'),
    ).toBeVisible();

    // Should display scope clauses
    await expect(page.locator('[data-testid="scope-clauses"]')).toBeVisible();
    await expect(page.locator('text="Scope of Work"')).toBeVisible();

    // Should display budget clauses
    await expect(page.locator('[data-testid="budget-clauses"]')).toBeVisible();
    await expect(page.locator('text="Payment Terms"')).toBeVisible();

    // Should display timeline clauses
    await expect(
      page.locator('[data-testid="timeline-clauses"]'),
    ).toBeVisible();
    await expect(page.locator('text="Project Schedule"')).toBeVisible();

    // Should show extraction confidence score
    await expect(
      page.locator('[data-testid="extraction-confidence"]'),
    ).toContainText("%");
  });

  test("should allow review and editing of extracted clauses [TEST-05]", async ({
    page,
  }) => {
    /**
     * RED Phase: User reviews and edits extracted clauses
     *
     * Expected: Can modify extracted clauses
     */
    // Navigate to clause review step
    await page.goto("http://localhost:3000/projects/new?step=clauses");

    // Click edit on first scope clause
    await page.click(
      '[data-testid="scope-clause-0"] [data-testid="edit-clause-button"]',
    );

    // Should open edit modal
    await expect(
      page.locator('[data-testid="edit-clause-modal"]'),
    ).toBeVisible();

    // Edit clause text
    await page.fill(
      '[data-testid="clause-text-input"]',
      "Updated scope description with additional requirements",
    );

    // Save changes
    await page.click('[data-testid="save-clause-button"]');

    // Modal should close
    await expect(
      page.locator('[data-testid="edit-clause-modal"]'),
    ).not.toBeVisible();

    // Updated text should be visible
    await expect(
      page.locator('text="Updated scope description"'),
    ).toBeVisible();

    // Can delete a clause
    await page.click(
      '[data-testid="budget-clause-0"] [data-testid="delete-clause-button"]',
    );

    // Should show confirmation
    await expect(
      page.locator('[data-testid="delete-confirmation-dialog"]'),
    ).toBeVisible();

    // Confirm deletion
    await page.click('[data-testid="confirm-delete-button"]');

    // Clause should be removed
    await expect(
      page.locator('[data-testid="budget-clause-0"]'),
    ).not.toBeVisible();
  });

  test("should generate initial WBS from clauses [TEST-06]", async ({
    page,
  }) => {
    /**
     * RED Phase: System generates WBS from extracted clauses
     *
     * Expected: WBS items created automatically
     */
    // Navigate to WBS generation step
    await page.goto("http://localhost:3000/projects/new?step=wbs");

    // Should show WBS generation preview
    await expect(
      page.locator('[data-testid="wbs-generation-preview"]'),
    ).toBeVisible();

    // Should show generated WBS tree
    await expect(page.locator('[data-testid="wbs-tree"]')).toBeVisible();

    // Should have root level items
    await expect(page.locator('[data-testid="wbs-item-code-1"]')).toBeVisible();
    await expect(page.locator('text="Project Management"')).toBeVisible();

    // Should have construction items
    await expect(page.locator('[data-testid="wbs-item-code-2"]')).toBeVisible();
    await expect(page.locator('text="Construction"')).toBeVisible();

    // Should show item count
    const itemCount = page.locator('[data-testid="wbs-item-count"]');
    await expect(itemCount).toContainText("items generated");

    // Can expand/collapse tree
    await page.click('[data-testid="wbs-expand-all-button"]');

    // Should show child items
    await expect(
      page.locator('[data-testid="wbs-item-code-1.1"]'),
    ).toBeVisible();
  });

  test("should complete project creation successfully [TEST-07]", async ({
    page,
  }) => {
    /**
     * RED Phase: User completes project creation
     *
     * Expected: Project created, redirected to dashboard
     */
    // Navigate to final review step
    await page.goto("http://localhost:3000/projects/new?step=review");

    // Should show project summary
    await expect(page.locator('[data-testid="project-summary"]')).toBeVisible();
    await expect(
      page.locator('text="Commercial Building Renovation"'),
    ).toBeVisible();

    // Should show WBS preview
    await expect(page.locator('[data-testid="wbs-summary"]')).toBeVisible();

    // Click create project button
    await page.click('[data-testid="create-project-button"]');

    // Should show creation progress
    await expect(
      page.locator('[data-testid="creation-progress"]'),
    ).toBeVisible();

    // Wait for creation to complete
    await page.waitForURL(/\/projects\/[^/?#]+$/, { timeout: 30000 });

    // Should be on project dashboard
    await expect(
      page.locator('[data-testid="project-dashboard"]'),
    ).toBeVisible();

    // Should show success notification
    await expect(
      page.locator('[data-testid="success-notification"]'),
    ).toContainText("Project created successfully");
  });

  test("should display onboarding tour for first-time users [TEST-08]", async ({
    page,
  }) => {
    /**
     * RED Phase: First-time onboarding tour displayed
     *
     * Expected: Tour modal appears after project creation
     */
    // Complete project creation first
    await page.goto("http://localhost:3000/projects/new?step=review");
    await page.click('[data-testid="create-project-button"]');
    await page.waitForURL(/\/projects\/[^/?#]+$/, { timeout: 30000 });

    // Should show onboarding tour modal
    await expect(
      page.locator('[data-testid="onboarding-tour-modal"]'),
    ).toBeVisible();

    // Should have tour title
    await expect(
      page.locator('h2:has-text("Welcome to Your New Project!")'),
    ).toBeVisible();

    // Should have tour steps
    await expect(page.locator('[data-testid="tour-step-1"]')).toBeVisible();
    await expect(
      page.locator('text="Explore your WBS structure"'),
    ).toBeVisible();

    // Can navigate to next step
    await page.click('[data-testid="tour-next-button"]');

    // Should show step 2
    await expect(page.locator('[data-testid="tour-step-2"]')).toBeVisible();

    // Can skip tour
    await page.click('[data-testid="tour-skip-button"]');

    // Modal should close
    await expect(
      page.locator('[data-testid="onboarding-tour-modal"]'),
    ).not.toBeVisible();
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================

// Test metadata for CI/CD integration
const testWithMeta = test as typeof test & {
  meta?: Record<string, string>;
};

testWithMeta.meta = {
  phase: "green",
  suite: "TS-E2E-J1-001",
  type: "e2e",
  priority: "p0",
};
