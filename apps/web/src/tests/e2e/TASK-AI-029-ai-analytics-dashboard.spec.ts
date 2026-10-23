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
    {
      bucket: "2026-04-21T00:00:00Z",
      model: "gpt-4o",
      prompt_version: "v2026.04.20",
      request_count: 30,
      total_tokens: 80000,
      total_cost: 8.5,
      avg_latency_ms: 350,
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
    {
      prompt_tag: "extraction",
      prompt_version: "v2026.04.15",
      total_runs: 30,
      success_rate: 0.98,
      avg_latency_ms: 280,
      total_cost: 5.2,
      feedback_count: 8,
      avg_feedback_score: 0.88,
    },
  ],
};

const DRIFT_PAYLOAD = {
  timeframe: "30d",
  window_start: "2026-03-22T00:00:00Z",
  // DriftDetector flags points beyond 1.5 population std devs. With only three
  // points no value can exceed sqrt(2) std devs, so a stable baseline precedes
  // the two outliers (the latency spike and the feedback drop).
  series: [
    { bucket: "2026-04-16T00:00:00Z", operation: "coherence", run_count: 100, avg_latency_ms: 410, avg_feedback_score: 0.92, feedback_count: 12 },
    { bucket: "2026-04-17T00:00:00Z", operation: "coherence", run_count: 100, avg_latency_ms: 400, avg_feedback_score: 0.91, feedback_count: 12 },
    { bucket: "2026-04-18T00:00:00Z", operation: "coherence", run_count: 100, avg_latency_ms: 420, avg_feedback_score: 0.93, feedback_count: 12 },
    { bucket: "2026-04-20T00:00:00Z", operation: "coherence", run_count: 100, avg_latency_ms: 415, avg_feedback_score: 0.92, feedback_count: 12 },
    { bucket: "2026-04-21T00:00:00Z", operation: "coherence", run_count: 50, avg_latency_ms: 1200, avg_feedback_score: 0.92, feedback_count: 5 },
    { bucket: "2026-04-22T00:00:00Z", operation: "extraction", run_count: 80, avg_latency_ms: 300, avg_feedback_score: 0.45, feedback_count: 20 },
  ],
  alerts: [
    { type: "feedback_drop", operation: "extraction", message: "Feedback score dropped by 11.4%" },
    { type: "latency_spike", operation: "coherence", message: "Latency increased by 195%" },
  ],
};

const USAGE_METRICS_PAYLOAD = {
  metrics: [
    {
      id: "1",
      timestamp: "2026-05-01T10:00:00Z",
      model: "claude-3-5-sonnet",
      prompt_version: "v2026.04.20",
      input_tokens: 1000,
      output_tokens: 500,
      total_tokens: 1500,
      cost: 0.0125,
      latency_ms: 350,
      trace_url: "https://smith.langchain.com/o/c2pro/traces/abc123",
    },
    {
      id: "2",
      timestamp: "2026-05-01T08:00:00Z",
      model: "gpt-4o",
      prompt_version: "v2026.04.15",
      input_tokens: 2000,
      output_tokens: 800,
      total_tokens: 2800,
      cost: 0.025,
      latency_ms: 450,
      trace_url: null,
    },
  ],
  total_count: 2,
  page: 1,
  page_size: 50,
};

test.describe("TASK-AI-029 AI analytics dashboard", () => {
  test("renders CostDashboard, VersionMonitor, DriftDetector, and UsageMetricsTable using mocked analytics APIs", async ({ page }) => {
    await page.route(/\/api(?:\/v1)?\/ai\/analytics\//, async (route) => {
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
      if (url.includes("/usage-metrics")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(USAGE_METRICS_PAYLOAD) });
        return;
      }
      await route.continue();
    });

    await page.goto("/ai-analytics", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "AI Analytics" })).toBeVisible();

    await expect(page.getByRole("heading", { name: "Cost Dashboard" })).toBeVisible();
    await expect(page.getByText("Total Cost:")).toContainText("$12.3456");
    // Version Monitor and Usage Metrics share labels (Version, Latency, Cost):
    // assert each panel within its own section.
    const panel = (name: string) =>
      page.getByRole("heading", { name }).locator("xpath=ancestor::section[1]");

    // The one cost chart: the app shell renders its own icon svgs.
    await expect(panel("Cost Dashboard").locator("svg")).toHaveCount(1);

    const versionMonitor = panel("Version Monitor");
    await expect(versionMonitor.getByRole("cell", { name: "v2026.04.20" })).toBeVisible();
    await expect(page.getByLabel("From:")).toBeVisible();
    await expect(page.getByLabel("To:")).toBeVisible();

    const driftDetector = panel("Drift Detector");
    await expect(driftDetector.getByText("Feedback score dropped by 11.4%")).toBeVisible();
    await expect(driftDetector.getByText("!", { exact: true })).toHaveCount(2);

    const usageMetrics = panel("Usage Metrics");
    await expect(usageMetrics.getByRole("button", { name: "Export CSV" })).toBeVisible();
    await expect(usageMetrics.getByRole("link", { name: "View Trace" })).toBeVisible();

    for (const column of [/Timestamp/, /Model/, /Tokens/, /Cost/, /Latency/, /Trace/]) {
      await expect(usageMetrics.getByRole("columnheader", { name: column })).toBeVisible();
    }
  });

  test("UsageMetricsTable sorting works correctly", async ({ page }) => {
    await page.route(/\/api(?:\/v1)?\/ai\/analytics\//, async (route) => {
      const url = route.request().url();
      if (url.includes("/usage-metrics")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(USAGE_METRICS_PAYLOAD) });
        return;
      }
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

    const modelHeader = page.getByRole("columnheader", { name: /Model/ });
    await expect(modelHeader).toBeVisible();

    // A new sort column starts ascending; clicking it again flips to descending.
    await modelHeader.click();
    await expect(page.getByRole("columnheader", { name: /Model/ })).toContainText("↑");
    await modelHeader.click();
    await expect(page.getByRole("columnheader", { name: /Model/ })).toContainText("↓");
  });

  test("trace_url deep-link opens in new tab", async ({ page }) => {
    await page.route(/\/api(?:\/v1)?\/ai\/analytics\//, async (route) => {
      const url = route.request().url();
      if (url.includes("/usage-metrics")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(USAGE_METRICS_PAYLOAD) });
        return;
      }
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

    const traceLink = page.getByRole("link", { name: "View Trace" }).first();
    await expect(traceLink).toBeVisible();

    const linkTarget = await traceLink.getAttribute("target");
    expect(linkTarget).toBe("_blank");
  });
});
