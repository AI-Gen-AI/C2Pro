import type {
  AICostAnalytics,
  AIQualityDrift,
  AIVersionPerformance,
} from "@/lib/api/contracts";
import { fetchApiJson } from "@/lib/api/services/http";

function withTimeframe(path: string, timeframe: string): string {
  return `${path}?timeframe=${encodeURIComponent(timeframe)}`;
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
