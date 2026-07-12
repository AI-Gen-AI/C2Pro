/**
 * Test Suite ID: TS-E2E-WEDGE-003
 * Coverage: E2E-W1..W5 Level-1 wedge journey.
 */
import { expect, test, type Page } from "@playwright/test";

const projectId = "proj-wedge-3";
const projectName = "Wedge Gate Pilot";

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

  await page.route("**/api/hitl/queue/review-wedge-1/approve", (route) => {
    approved = true;
    return route.fulfill({
      json: {
        item_id: "review-wedge-1",
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

test("E2E-W1..W5 typed triplet to report export", async ({ page }) => {
  await installWedgeRoutes(page);

  await page.goto(`/projects/${projectId}/documents`);
  await expect(page.getByTestId("documents-page")).toBeVisible();
  await expect(page.getByText(/triplet complete/i)).toBeVisible();
  await expect(page.getByText("baseline-contract.pdf")).toBeVisible();
  await expect(page.getByText("validated-budget.xlsx")).toBeVisible();
  await expect(page.getByText("approved-schedule.xlsx")).toBeVisible();

  await page.getByRole("button", { name: /evaluate coherence/i }).click();

  await page.goto(`/projects/${projectId}/coherence?cohV1Scenario=full-triplet`);
  await expect(page.getByText(/coherence score v1 is active/i).first()).toBeVisible();
  await expect(page.getByLabel(/v1 exponential-decay coherence score/i)).toBeVisible();

  await page.goto(`/projects/${projectId}/documents`);
  await page.getByRole("link", { name: /baseline-contract.pdf/i }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/evidence\\?documentId=doc-contract`));

  await page.goto(`/projects/${projectId}/review`);
  await expect(page.getByTestId("review-page")).toBeVisible();
  await expect(page.getByText(/budget deviation has supporting evidence/i)).toBeVisible();
  await page.getByTestId("approve-review-wedge-1").click();
  await expect(page.getByRole("dialog", { name: /approve review item/i })).toBeVisible();
  await page.getByRole("button", { name: /confirm approve/i }).click();
  await expect(page.getByTestId("stat-approved")).toContainText("1");

  await page.goto(`/projects/${projectId}/report`);
  await expect(page.getByRole("heading", { name: /audit report/i })).toBeVisible();
  await expect(page.getByText(projectName)).toBeVisible();
  await expect(page.getByRole("button", { name: /download json/i })).toBeEnabled();
});

test.skip("E2E-W3..W5 @real-backend validates the same wedge against a live backend", async () => {
  // TODO(TASK-FRT-192): enable in the scheduled real-backend workflow
  // after the backend fixture can seed a typed triplet, HITL item, and report payload.
});
