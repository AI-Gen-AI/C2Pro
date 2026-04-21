"use client";

import { useEffect, useState } from "react";
import type { AICostAnalytics, AIQualityDrift, AIVersionPerformance } from "@/lib/api/contracts";
import { getCostAnalytics, getQualityDrift, getVersionPerformance } from "@/lib/api/services/ai-analytics";
import { CostDashboard } from "@/components/features/ai-analytics/CostDashboard";
import { DriftDetector } from "@/components/features/ai-analytics/DriftDetector";
import { VersionMonitor } from "@/components/features/ai-analytics/VersionMonitor";

const EMPTY_COST: AICostAnalytics = {
  timeframe: "30d",
  window_start: new Date(0).toISOString(),
  summary: { total_cost: 0, total_tokens: 0, total_requests: 0 },
  series: [],
};
const EMPTY_VERSIONS: AIVersionPerformance = { timeframe: "30d", window_start: new Date(0).toISOString(), versions: [] };
const EMPTY_DRIFT: AIQualityDrift = { timeframe: "30d", window_start: new Date(0).toISOString(), series: [], alerts: [] };

export default function AIAnalyticsPage() {
  const [timeframe, setTimeframe] = useState("30d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cost, setCost] = useState<AICostAnalytics>(EMPTY_COST);
  const [versions, setVersions] = useState<AIVersionPerformance>(EMPTY_VERSIONS);
  const [drift, setDrift] = useState<AIQualityDrift>(EMPTY_DRIFT);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getCostAnalytics(timeframe),
      getVersionPerformance(timeframe),
      getQualityDrift(timeframe),
    ])
      .then(([costData, versionData, driftData]) => {
        if (!active) return;
        setCost(costData ?? EMPTY_COST);
        setVersions(versionData ?? EMPTY_VERSIONS);
        setDrift(driftData ?? EMPTY_DRIFT);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load analytics data.");
        setCost(EMPTY_COST);
        setVersions(EMPTY_VERSIONS);
        setDrift(EMPTY_DRIFT);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [timeframe]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">AI Analytics</h1>
        <select
          value={timeframe}
          onChange={(event) => setTimeframe(event.target.value)}
          className="rounded border bg-background px-3 py-2 text-sm"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
        </select>
      </div>

      <CostDashboard data={cost} loading={loading} error={error} />
      <VersionMonitor data={versions} loading={loading} error={error} />
      <DriftDetector data={drift} loading={loading} error={error} />
    </div>
  );
}
