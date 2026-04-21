/**
 * TS-AI-LANGSMITH-VALIDATION-E2E
 * TASK-AI-029: Validate AI analytics dashboard rendering with deterministic mocked API payloads.
 */
import { expect, test } from "@playwright/test";

const COST_PAYLOAD = {
  timeframe: "30d",
  window_start: "2026-03-22T00:00:00Z",
  summary: { total_cost: 12.3456, total_tokens: 123456, total_requests: 42 },
  series: [
    {
      bucket: "2026-04-20T00:00:00Z",
      model: "claude-3-5-sonnet",
      prompt_version: "v2026.04.20",
      request_count: 42,
      total_tokens: 123456,
      total_cost: 12.3456,
      avg_latency_ms: 410,
    },
  ],
};

const VERSION_PAYLOAD = {
  timeframe: "30d",
  window_start: "2026-03-22T00:00:00Z",
  versions: [
    {
      prompt_tag: "coherence",
      prompt_version: "v2026.04.20",
      total_runs: 42,
      success_rate: 0.975,
      avg_latency_ms: 410,
      total_cost: 12.3456,
      feedback_count: 12,
      avg_feedback_score: 0.92,
    },
  ],
};

const DRIFT_PAYLOAD = {
  timeframe: "30d",
  window_start: "2026-03-22T00:00:00Z",
  series: [{ bucket: "2026-04-20T00:00:00Z", operation: "coherence", avg_feedback_score: 0.92, feedback_count: 12 }],
  alerts: [{ type: "feedback_drop", operation: "coherence", message: "Feedback score dropped by 11.4%" }],
};

test.describe("TASK-AI-029 AI analytics dashboard", () => {
  test("renders CostDashboard, VersionMonitor, and DriftDetector using mocked analytics APIs", async ({ page }) => {
    await page.route("**/api/v1/ai/analytics/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/cost")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(COST_PAYLOAD) });
        return;
      }
      if (url.includes("/versions")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(VERSION_PAYLOAD) });
        return;
      }
      if (url.includes("/quality-drift")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(DRIFT_PAYLOAD) });
        return;
      }
      await route.continue();
    });

    await page.goto("/ai-analytics", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "AI Analytics" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Cost Dashboard" })).toBeVisible();
    await expect(page.getByText("Total Cost:")).toContainText("$12.3456");
    await expect(page.getByRole("heading", { name: "Version Monitor" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "v2026.04.20" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Drift Detector" })).toBeVisible();
    await expect(page.getByText("Feedback score dropped by 11.4%")).toBeVisible();
  });
});
