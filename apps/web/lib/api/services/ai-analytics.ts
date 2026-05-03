import type {
  AICostAnalytics,
  AIQualityDrift,
  AIVersionPerformance,
  AIUsageMetricsResponse,
} from "@/lib/api/contracts";
import { fetchApiJson } from "@/lib/api/services/http";

function withTimeframe(path: string, timeframe: string): string {
  return `${path}?timeframe=${encodeURIComponent(timeframe)}`;
}

function withPagination(path: string, page: number, pageSize: number): string {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}page=${page}&page_size=${pageSize}`;
}

export function getCostAnalytics(timeframe: string): Promise<AICostAnalytics> {
  return fetchApiJson<AICostAnalytics>(withTimeframe("ai/analytics/cost", timeframe));
}

export function getVersionPerformance(timeframe: string): Promise<AIVersionPerformance> {
  return fetchApiJson<AIVersionPerformance>(withTimeframe("ai/analytics/versions", timeframe));
}

export function getQualityDrift(timeframe: string): Promise<AIQualityDrift> {
  return fetchApiJson<AIQualityDrift>(withTimeframe("ai/analytics/quality-drift", timeframe));
}

export function getUsageMetrics(
  timeframe: string,
  page = 1,
  pageSize = 50,
): Promise<AIUsageMetricsResponse> {
  return fetchApiJson<AIUsageMetricsResponse>(
    withPagination(withTimeframe("ai/analytics/usage-metrics", timeframe), page, pageSize),
  );
}
