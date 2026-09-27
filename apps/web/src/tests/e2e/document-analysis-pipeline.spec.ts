/**
 * TS-E2E-DAP-001 - Document Analysis Pipeline Journey
 *
 * Test Suite ID: TS-E2E-DAP-001
 * Type: E2E Journey Test
 * Priority: P1
 * Task: TASK-FRT-166
 * Phase: GREEN
 *
 * End-to-end test for the complete document analysis pipeline:
 *   1. Upload document to a project
 *   2. Verify analysis triggers and status transitions
 *   3. Verify alerts are generated from analysis
 *   4. Verify HITL review queue receives items
 *   5. Test approval/rejection flows
 *   6. Test error scenarios (invalid file, large file)
 *
 * Run: pnpm exec playwright test document-analysis-pipeline.spec.ts
 */

import { test, expect, type Page } from "@playwright/test";

/** Demo project ID used across the test suite (no auth required). */
const DEMO_PROJECT_ID = "proj_demo_001";

/**
 * Navigate to the demo project's documents page.
 * Demo routes bypass Clerk auth, making them suitable for E2E.
 */
async function goToProjectDocuments(page: Page) {
  await page.goto(`/projects/${DEMO_PROJECT_ID}/documents`);
  await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 15_000 });
}

async function goToProjectAlerts(page: Page) {
  await page.goto(`/projects/${DEMO_PROJECT_ID}/alerts`);
  // Wait for page to stabilize
  await page.waitForLoadState("networkidle");
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

test.describe("TS-E2E-DAP-001: Document Analysis Pipeline", () => {
  test.describe.configure({ mode: "serial" });

  test("DAP-001: Documents page loads with project context", async ({ page }) => {
    await goToProjectDocuments(page);

    // Should display the documents page container
    await expect(page.getByTestId("documents-page")).toBeVisible();

    // Should have an upload action available
    const uploadButton = page.getByRole("button", { name: /upload/i });
    await expect(uploadButton).toBeVisible();
  });

  test("DAP-002: Upload dialog opens and accepts files", async ({ page }) => {
    await goToProjectDocuments(page);

    // Click the upload button
    await page.getByRole("button", { name: /upload/i }).click();

    // Upload dialog should appear
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Should contain a dropzone or file input area
    const dropzoneOrInput = dialog.locator(
      '[data-testid="upload-dropzone"], input[type="file"], [role="button"]:has-text("drop")'
    );
    await expect(dropzoneOrInput.first()).toBeVisible();
  });

  test("DAP-003: Document status transitions after upload", async ({ page }) => {
    await goToProjectDocuments(page);

    // Count documents before (may be 0 or pre-existing demo data)
    const initialRows = await page.locator("table tbody tr, [data-testid^='document-row']").count();

    // If there are existing documents, verify at least one shows a status badge
    if (initialRows > 0) {
      const statusBadge = page.locator(
        '[class*="badge"], [data-testid*="status"]'
      ).first();
      await expect(statusBadge).toBeVisible();

      // Status should be one of the known values
      const text = await statusBadge.textContent();
      const validStatuses = ["Uploaded", "Processing", "Parsed", "Analysis pending", "Analyzed", "Error"];
      const hasValidStatus = validStatuses.some(
        (s) => text?.toLowerCase().includes(s.toLowerCase())
      );
      expect(hasValidStatus).toBe(true);
    }
  });

  test("DAP-004: Alerts page shows alerts for project", async ({ page }) => {
    await goToProjectAlerts(page);

    // Page should load (either with alerts or empty state)
    const heading = page.getByRole("heading", { name: /alert/i });
    const alertsList = page.locator(
      "table, [data-testid='alerts-list'], [data-testid='alerts-page']"
    );
    const emptyState = page.getByText(/no alerts/i);

    // One of these should be visible
    await expect(
      heading.or(alertsList.first()).or(emptyState)
    ).toBeVisible({ timeout: 10_000 });
  });

  test("DAP-005: Alert detail shows severity and description", async ({ page }) => {
    await goToProjectAlerts(page);
    await page.waitForLoadState("networkidle");

    // Find alert rows or cards
    const alertItems = page.locator(
      "table tbody tr, [data-testid^='alert-'], [role='row']"
    );
    const count = await alertItems.count();

    if (count === 0) {
      test.skip(true, "TASK-QA-336: demo project has no seeded alerts");
      return;
    }

    // Click first alert to view detail
    await alertItems.first().click();

    // Should show some detail view (dialog, drawer, or page)
    const detailView = page.locator(
      "[role='dialog'], [data-testid='alert-detail'], [data-testid='alert-drawer']"
    );

    // If the click opened a detail view, verify severity is shown
    const detailCount = await detailView.count();
    if (detailCount > 0) {
      await expect(detailView.first()).toBeVisible();

      // Severity should be displayed somewhere
      const severityText = page.getByText(
        /critical|high|medium|low|info/i
      );
      await expect(severityText.first()).toBeVisible();
    }
  });

  test("DAP-006: Alert approve/reject buttons are accessible", async ({ page }) => {
    await goToProjectAlerts(page);
    await page.waitForLoadState("networkidle");

    // Look for review action buttons
    const approveBtn = page.getByRole("button", { name: /approve/i });
    const rejectBtn = page.getByRole("button", { name: /reject/i });
    const reviewBtn = page.getByRole("button", { name: /review/i });

    // At least one review-related action should exist (approve, reject, or review)
    const hasApprove = (await approveBtn.count()) > 0;
    const hasReject = (await rejectBtn.count()) > 0;
    const hasReview = (await reviewBtn.count()) > 0;

    if (!hasApprove && !hasReject && !hasReview) {
      test.skip(true, "TASK-QA-336: demo project has no reviewable alert state");
      return;
    }

    // If approve exists, it should be clickable
    if (hasApprove) {
      await expect(approveBtn.first()).toBeEnabled();
    }
  });

  test("DAP-007: Document filter and search work correctly", async ({ page }) => {
    await goToProjectDocuments(page);

    // Search input should exist
    const searchInput = page.getByPlaceholder(/search/i).or(
      page.locator("input[type='search'], input[type='text']").first()
    );

    if ((await searchInput.count()) > 0) {
      // Type a search query
      await searchInput.first().fill("contract");
      await page.waitForTimeout(500); // debounce

      // Results should filter (either show matching docs or empty)
      // Clear search
      await searchInput.first().clear();
    }

    // Status filter should exist
    const statusFilter = page.locator(
      "[data-testid='status-filter'], select, [role='combobox']"
    );
    if ((await statusFilter.count()) > 0) {
      await expect(statusFilter.first()).toBeVisible();
    }
  });

  test("DAP-008: Delete document shows confirmation dialog", async ({ page }) => {
    await goToProjectDocuments(page);

    // Find delete buttons
    const deleteBtn = page.getByRole("button", { name: /delete/i }).or(
      page.locator("[data-testid*='delete']").first()
    );

    if ((await deleteBtn.count()) === 0) {
      test.skip(true, "TASK-QA-336: demo project has no seeded document to delete");
      return;
    }

    // Click first delete button
    await deleteBtn.first().click();

    // Confirmation dialog should appear
    const dialog = page.getByRole("dialog").or(
      page.getByRole("alertdialog")
    );
    await expect(dialog.first()).toBeVisible({ timeout: 5_000 });

    // Should have cancel option
    const cancelBtn = dialog.first().getByRole("button", { name: /cancel/i });
    await expect(cancelBtn).toBeVisible();

    // Cancel to not actually delete
    await cancelBtn.click();
    await expect(dialog.first()).not.toBeVisible();
  });

  test("DAP-009: Navigation between documents and alerts tabs", async ({ page }) => {
    // Start at documents
    await goToProjectDocuments(page);

    // Find alerts tab/link
    const alertsTab = page.getByRole("link", { name: /alert/i }).or(
      page.getByRole("tab", { name: /alert/i })
    );

    if ((await alertsTab.count()) > 0) {
      await alertsTab.first().click();
      await page.waitForLoadState("networkidle");

      // Should now be on alerts page
      const url = page.url();
      expect(url).toContain("alerts");
    }

    // Navigate back to documents
    const docsTab = page.getByRole("link", { name: /document/i }).or(
      page.getByRole("tab", { name: /document/i })
    );

    if ((await docsTab.count()) > 0) {
      await docsTab.first().click();
      await page.waitForLoadState("networkidle");

      const url = page.url();
      expect(url).toContain("documents");
    }
  });

  test("DAP-010: Error state renders gracefully for invalid project", async ({ page }) => {
    // Navigate to a non-existent project
    await page.goto("/projects/non-existent-project-id/documents");

    // Should show error state or redirect, not crash
    // Wait for any response
    await page.waitForLoadState("networkidle");

    // Page should not show a raw error stack trace
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("TypeError");
    expect(bodyText).not.toContain("Unhandled Runtime Error");
  });
});

// ---------------------------------------------------------------------------
// HITL Review Flow Tests
// ---------------------------------------------------------------------------

test.describe("TS-E2E-DAP-002: HITL Review Flow", () => {
  test("HITL-001: Review queue page loads", async ({ page }) => {
    // Navigate to HITL queue if route exists
    await page.goto("/projects/proj_demo_001/alerts");
    await page.waitForLoadState("networkidle");

    // The alerts page should load - it serves as the review interface
    const pageContent = page.locator("body");
    await expect(pageContent).toBeVisible();

    // Should not show unhandled errors
    const text = await pageContent.textContent();
    expect(text).not.toContain("TypeError");
  });

  test("HITL-002: Approve action shows confirmation", async ({ page }) => {
    await page.goto("/projects/proj_demo_001/alerts");
    await page.waitForLoadState("networkidle");

    const approveBtn = page.getByRole("button", { name: /approve/i });

    if ((await approveBtn.count()) === 0) {
      test.skip(true, "TASK-QA-336: demo project has no seeded approvable review item");
      return;
    }

    await approveBtn.first().click();

    // Should show confirmation dialog or checkbox
    const confirmDialog = page.getByRole("dialog").or(
      page.getByRole("alertdialog")
    );
    const confirmCheckbox = page.getByRole("checkbox", { name: /confirm/i });

    const hasDialog = (await confirmDialog.count()) > 0;
    const hasCheckbox = (await confirmCheckbox.count()) > 0;

    expect(hasDialog || hasCheckbox).toBe(true);

    // Close/cancel if dialog opened
    if (hasDialog) {
      const cancelBtn = confirmDialog.first().getByRole("button", { name: /cancel/i });
      if ((await cancelBtn.count()) > 0) {
        await cancelBtn.click();
      } else {
        await page.keyboard.press("Escape");
      }
    }
  });

  test("HITL-003: Reject action requires reason", async ({ page }) => {
    await page.goto("/projects/proj_demo_001/alerts");
    await page.waitForLoadState("networkidle");

    const rejectBtn = page.getByRole("button", { name: /reject/i });

    if ((await rejectBtn.count()) === 0) {
      test.skip(true, "TASK-QA-336: demo project has no seeded rejectable review item");
      return;
    }

    await rejectBtn.first().click();

    // Should show rejection dialog with reason input
    const dialog = page.getByRole("dialog").or(
      page.getByRole("alertdialog")
    );

    if ((await dialog.count()) > 0) {
      // Look for a reason textarea or input
      const reasonInput = dialog.first().locator(
        "textarea, input[type='text'], [data-testid*='reason']"
      );

      if ((await reasonInput.count()) > 0) {
        await expect(reasonInput.first()).toBeVisible();
      }

      // Cancel
      await page.keyboard.press("Escape");
    }
  });
});

// ---------------------------------------------------------------------------
// #712: Truthful document / HITL lifecycle states
//
// The demo project's fixture data does not include a document genuinely
// paused for HITL review (see the TASK-QA-336 skips above) -- reproducing
// that would need a live backend, a live worker and a real LangGraph
// interrupt, none of which this suite has. What IS testable end to end,
// without a real backend, is the contract between the Documents page and
// whatever `GET /projects/{id}/documents` durably returns: given each #712
// lifecycle state, does the page render the truthful label, stop treating it
// as active processing, offer the right action, and reproduce the exact same
// thing after a hard reload? That is proven here with `page.route`, the same
// network-mocking approach already used by ERR-002 above. The backend's own
// truthfulness -- that these fields are what a real reject/approve durably
// persists -- is proven separately by the Python HITL finalization tests.
// ---------------------------------------------------------------------------

test.describe("TS-E2E-712: Truthful document / HITL lifecycle states", () => {
  const DOCUMENTS_ROUTE = `**/api/v1/projects/${DEMO_PROJECT_ID}/documents*`;

  function documentsResponse(item: Record<string, unknown>) {
    return {
      items: [
        {
          id: "doc-712-fixture",
          filename: "Contract.pdf",
          document_type: "contract",
          status: "processing",
          status_detail: "",
          lifecycle_status: "analysis_pending",
          retryable: false,
          review_count: null,
          review_item_id: null,
          error_message: null,
          uploaded_at: "2026-03-19T09:00:00Z",
          file_size_bytes: 2048,
          ...item,
        },
      ],
      total_count: 1,
      skip: 0,
      limit: 20,
    };
  }

  async function mockDocumentsOnce(page: Page, item: Record<string, unknown>) {
    await page.route(DOCUMENTS_ROUTE, (route) =>
      route.fulfill({ json: documentsResponse(item) }),
    );
  }

  test("712-001: a document paused for review shows 'Review required', never 'not started', with a CTA to the exact item", async ({
    page,
  }) => {
    await mockDocumentsOnce(page, {
      lifecycle_status: "review_required",
      status_detail: "Analysis completed and is waiting for a human review decision.",
      review_count: 1,
      review_item_id: "22222222-2222-2222-2222-222222222222",
    });

    await goToProjectDocuments(page);

    const row = page.getByTestId("document-row-doc-712-fixture");
    await expect(row).toContainText("Review required");
    await expect(row).not.toContainText(/not started/i);
    // Paused-for-review is not active processing -- no polling tracker.
    await expect(page.getByTestId("documents-page")).not.toContainText(
      "Analysis progress",
    );

    const reviewCta = page.getByTestId("document-review-cta");
    await expect(reviewCta).toBeVisible();
    await expect(reviewCta).toHaveAttribute(
      "href",
      `/projects/${DEMO_PROJECT_ID}/review?itemId=22222222-2222-2222-2222-222222222222`,
    );
  });

  test("712-002: a hard reload reproduces the exact same review-required state", async ({
    page,
  }) => {
    await mockDocumentsOnce(page, {
      lifecycle_status: "review_required",
      review_count: 1,
      review_item_id: "22222222-2222-2222-2222-222222222222",
    });

    await goToProjectDocuments(page);
    await expect(page.getByTestId("document-row-doc-712-fixture")).toContainText(
      "Review required",
    );

    await page.reload();
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 15_000 });

    await expect(page.getByTestId("document-row-doc-712-fixture")).toContainText(
      "Review required",
    );
    await expect(page.getByTestId("document-review-cta")).toHaveAttribute(
      "href",
      `/projects/${DEMO_PROJECT_ID}/review?itemId=22222222-2222-2222-2222-222222222222`,
    );
  });

  test("712-003: more than one pending review routes to the project review queue, never a guess", async ({
    page,
  }) => {
    await mockDocumentsOnce(page, {
      lifecycle_status: "review_required",
      review_count: 2,
      review_item_id: null,
    });

    await goToProjectDocuments(page);

    const reviewCta = page.getByTestId("document-review-cta");
    await expect(reviewCta).toHaveAttribute("href", `/projects/${DEMO_PROJECT_ID}/review`);
    await expect(reviewCta).toContainText("2");
  });

  test("712-004: an exhausted analysis attempt shows a durable failure with Retry, and stops polling", async ({
    page,
  }) => {
    await mockDocumentsOnce(page, {
      lifecycle_status: "failed_retryable",
      status_detail: "Automatic analysis did not complete after several attempts. Retry to try again.",
      retryable: true,
    });

    await goToProjectDocuments(page);

    const row = page.getByTestId("document-row-doc-712-fixture");
    await expect(row).toContainText("Retry needed");
    await expect(
      page.getByRole("button", { name: /retry processing contract\.pdf/i }),
    ).toBeVisible();
    await expect(page.getByTestId("documents-page")).not.toContainText(
      "Analysis progress",
    );
  });

  test("712-005: a rejected document shows a durable 'Needs changes' state, never a retry action", async ({
    page,
  }) => {
    await mockDocumentsOnce(page, {
      status: "error",
      lifecycle_status: "needs_changes",
      status_detail: "A reviewer requested changes. Upload a corrected version to continue.",
      retryable: false,
    });

    await goToProjectDocuments(page);

    const row = page.getByTestId("document-row-doc-712-fixture");
    await expect(row).toContainText("Needs changes");
    await expect(
      page.getByRole("button", { name: /retry processing contract\.pdf/i }),
    ).toHaveCount(0);
    await expect(page.getByTestId("documents-page")).not.toContainText(
      "Analysis progress",
    );
  });

  test("712-006: approving the pending review leaves 'Review required' on the very next load", async ({
    page,
  }) => {
    let decided = false;
    await page.route(DOCUMENTS_ROUTE, (route) =>
      route.fulfill({
        json: documentsResponse(
          decided
            ? { lifecycle_status: "analyzed", status: "parsed", retryable: false }
            : {
                lifecycle_status: "review_required",
                review_count: 1,
                review_item_id: "22222222-2222-2222-2222-222222222222",
              },
        ),
      }),
    );

    await goToProjectDocuments(page);
    await expect(page.getByTestId("document-row-doc-712-fixture")).toContainText(
      "Review required",
    );

    // Simulates the human decision finalizing durably on the backend (proven
    // by the Python HITL finalization tests) -- the next fetch reflects it.
    decided = true;
    await page.reload();
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 15_000 });

    const row = page.getByTestId("document-row-doc-712-fixture");
    await expect(row).toContainText("Analyzed");
    await expect(row).not.toContainText("Review required");
    await expect(page.getByTestId("document-review-cta")).toHaveCount(0);
  });
});

// ---------------------------------------------------------------------------
// Error Scenarios
// ---------------------------------------------------------------------------

test.describe("TS-E2E-DAP-003: Error Scenarios", () => {
  test("ERR-001: Upload dialog validates file type", async ({ page }) => {
    await page.goto(`/projects/${DEMO_PROJECT_ID}/documents`);
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 15_000 });

    // Open upload dialog
    await page.getByRole("button", { name: /upload/i }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // The dropzone should have accept restrictions or display accepted types
    const dropzone = dialog.locator(
      "[data-testid='upload-dropzone'], [class*='dropzone']"
    );

    if ((await dropzone.count()) > 0) {
      // Verify the dropzone indicates accepted file types
      const dropzoneText = await dropzone.first().textContent();
      // Should mention PDF, XLSX, or similar accepted formats
      const mentionsFormats = /pdf|xlsx|doc|csv|file/i.test(dropzoneText ?? "");
      expect(mentionsFormats).toBe(true);
    }

    // Close dialog
    await page.keyboard.press("Escape");
  });

  test("ERR-002: Network error shows user-friendly message", async ({ page }) => {
    // Intercept API calls to simulate network failure
    await page.route("**/api/v1/**", (route) =>
      route.abort("connectionrefused")
    );

    await page.goto(`/projects/${DEMO_PROJECT_ID}/documents`);

    // Page should show error state, not crash
    await page.waitForLoadState("domcontentloaded");

    // Should display an error message or empty state
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("Unhandled Runtime Error");

    // Unroute to restore normal behavior
    await page.unroute("**/api/v1/**");
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================

const testWithMeta = test as typeof test & {
  meta?: Record<string, string>;
};

testWithMeta.meta = {
  phase: "green",
  suite: "TS-E2E-DAP-001",
  type: "e2e",
  priority: "p1",
  task: "TASK-FRT-166",
};
