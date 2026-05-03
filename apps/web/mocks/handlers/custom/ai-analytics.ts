import { http, HttpResponse } from "@/mocks/msw";

const generateMockUsageMetrics = () => {
  const models = ["claude-3-5-sonnet", "claude-3-opus", "gpt-4o", "gpt-4-turbo"];
  const versions = ["v2026.04.20", "v2026.04.15", "v2026.04.10", "v2026.04.05"];
  const metrics = [];

  for (let i = 0; i < 25; i++) {
    const timestamp = new Date();
    timestamp.setHours(timestamp.getHours() - i * 2);

    const model = models[i % models.length];
    const version = versions[i % versions.length];
    const inputTokens = Math.floor(Math.random() * 5000) + 500;
    const outputTokens = Math.floor(Math.random() * 3000) + 100;
    const totalTokens = inputTokens + outputTokens;
    const cost = (inputTokens * 0.000003 + outputTokens * 0.000015);
    const latency = Math.floor(Math.random() * 800) + 200;

    metrics.push({
      id: `metric_${i + 1}`,
      timestamp: timestamp.toISOString(),
      model,
      prompt_version: version,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      total_tokens: totalTokens,
      cost: Number(cost.toFixed(4)),
      latency_ms: latency,
      trace_url: `https://smith.langchain.com/o/c2pro/traces/${Math.random().toString(36).substring(7)}`,
    });
  }

  return metrics;
};

const mockMetrics = generateMockUsageMetrics();

export const aiAnalyticsHandlers = [
  http.get("/api/v1/ai/analytics/usage-metrics", ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get("page") ?? "1", 10);
    const pageSize = parseInt(url.searchParams.get("page_size") ?? "50", 10);

    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const paginatedMetrics = mockMetrics.slice(start, end);

    return HttpResponse.json({
      metrics: paginatedMetrics,
      total_count: mockMetrics.length,
      page,
      page_size: pageSize,
    });
  }),
];